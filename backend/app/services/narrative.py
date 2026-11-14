from collections.abc import Awaitable, Callable
import json
import logging
import re
from typing import Literal

import httpx

from app.core.config import settings
from app.schemas.patient import PatientTrendBadge

logger = logging.getLogger(__name__)

# Enam aturan system prompt sesuai Tabel 3.4 proposal (Bab 3.8)
SYSTEM_PROMPT_TABEL_3_4 = """Anda adalah asisten dokumentasi klinis untuk pemantauan longitudinal ulkus kusta.
Hasilkan keluaran HANYA dalam format JSON valid dengan tepat dua kunci: "clinician_notes" dan "patient_narrative".
Wajib patuhi enam aturan Tabel 3.4 berikut tanpa pengecualian:
1. Kepatuhan Angka: Menggunakan angka sesuai data masukan (A0, A_t, delta_A, PAC) tanpa mengubah atau menambahkan angka baru. Jika masukan tidak memuat field "satuan" (atau "satuan" = "%"), A0 dan A_t dinyatakan dalam satuan %, delta_A dalam poin persentase, dan PAC dalam % (dilarang menggunakan satuan cm atau cm²). Jika masukan memuat "satuan": "cm²", A0, A_t, dan delta_A wajib ditulis dalam satuan cm², PAC tetap dalam %, dan istilah "poin persentase" dilarang. Seluruh angka desimal dalam teks narasi wajib ditulis menggunakan tanda koma (contoh: 26,37%), tanpa pemisah ribuan.
2. Larangan Diagnosis: Tidak memberikan diagnosis medis maupun meresepkan obat.
3. Bahasa Observasional: Menggunakan istilah pengamatan fisik, seperti "terdeteksi mengecil", "terukur membesar", atau "relatif stabil". Dilarang memakai kata "membaik", "memburuk", "sembuh", "infeksi", "diagnosis" (kecuali dalam frasa disclaimer "bukan diagnosis medis"), atau "resep".
4. Disclaimer Medis: Menyertakan keterangan di kedua narasi bahwa hasil merupakan estimasi visual sistem berdasarkan foto dan memerlukan pemeriksaan langsung oleh tenaga medis (perawat atau dokter), serta bukan diagnosis medis.
5. Narasi Pasien (patient_narrative): Menggunakan bahasa Indonesia sehari-hari yang sederhana, empatik, dan mudah dipahami, serta mencantumkan nilai mutlak PAC (tanpa tanda minus '-'). Dilarang memuat kalimat menenangkan ("tenang", "jangan khawatir", "tidak perlu cemas", "baik-baik saja") pada semua status tren. Pada Tren Meningkat, patient_narrative wajib memuat ajakan berkonsultasi dengan perawat atau dokter.
6. Catatan Klinisi (clinician_notes): Menggunakan bahasa formal dan ringkas dengan mencantumkan nilai A0, A_t, delta_A (dengan tanda + atau -), dan PAC (wajib diawali tanda '+' jika PAC > 0 atau '-' jika PAC < 0 sesuai tanda pada data masukan)."""

FORBIDDEN_WORDS = (
    "membaik",
    "memburuk",
    "sembuh",
    "infeksi",
    "diagnosis",
    "resep",
    "tenang",
    "jangan khawatir",
    "tidak perlu cemas",
    "baik-baik saja",
)

# Toleransi presisi perbandingan angka pasca-normalisasi koma/titik (menolak selisih >= 0.01 seperti 26,38 vs 26.37)
NUMBER_ROUNDING_TOLERANCE = 0.004

NarrativeServiceFn = Callable[
    ...,
    Awaitable[tuple[str, str, str]],
]


def build_gemini_user_prompt(
    a0: float,
    at: float,
    delta_a: float,
    pac: float,
    trend_status: str,
    unit: Literal["%", "cm²"] = "%",
) -> dict[str, float | str]:
    """
    Membuat muatan user prompt ke Gemini:
    - Mode relatif (unit="%"): tepat lima field (A0, A_t, delta_A, PAC, trend_status).
    - Mode terkalibrasi (unit="cm²"): lima field di atas + string satuan ("satuan": "cm²") sesuai Keputusan D3.
    Tanpa PII, nama, kode RM, koordinat kalibrasi, skala, atau citra.
    """
    payload: dict[str, float | str] = {
        "A0": round(a0, 2),
        "A_t": round(at, 2),
        "delta_A": round(delta_a, 2),
        "PAC": round(pac, 2),
        "trend_status": trend_status,
    }
    if unit == "cm²":
        payload["satuan"] = "cm²"
    return payload


def extract_numbers_from_text(text: str) -> list[float]:
    """
    Mengekstrak seluruh angka (integer maupun desimal dengan titik atau koma) dari teks,
    setelah mengabaikan token notasi indeks tetap seperti 'T₁', 'T1', 'A₀', atau 'A0'.
    """
    cleaned = re.sub(r"\b(?:T[₁1]|A[₀0])\b", "ID_AWAL", text)
    matches = re.findall(r"(?<![A-Za-z_])\d+(?:[.,]\d+)?", cleaned)
    result: list[float] = []
    for token in matches:
        normalized = token.replace(",", ".")
        try:
            result.append(float(normalized))
        except ValueError:
            continue
    return result


def _contains_forbidden_word(text: str) -> str | None:
    lowered = text.lower()
    # Izinkan frasa disclaimer resmi "bukan diagnosis medis" / "bukan merupakan diagnosis medis"
    sanitized = re.sub(
        r"\bbukan(?:lah)?(?:\s+merupakan)?\s+diagnosis(?:\s+medis)?\b", "", lowered
    )
    for word in FORBIDDEN_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", sanitized):
            return word
    return None


def _has_required_disclaimer(text: str) -> bool:
    lowered = text.lower()
    has_estimation = "estimasi" in lowered and "foto" in lowered
    has_clinical_follow_up = any(
        kw in lowered
        for kw in ("pemeriksaan", "perawat", "dokter", "tenaga medis", "bukan diagnosis")
    )
    return has_estimation and has_clinical_follow_up


def _has_meningkat_consultation_call(patient_narrative: str) -> bool:
    lowered = patient_narrative.lower()
    has_action = any(kw in lowered for kw in ("konsultasi", "periksakan", "hubungi"))
    has_clinician = any(kw in lowered for kw in ("perawat", "dokter", "tenaga medis"))
    return has_action and has_clinician


def _normalize_minus(text: str) -> str:
    """Menormalisasi tanda minus Unicode (U+2212) dan en-dash (U+2013) ke hyphen ASCII '-'."""
    return text.replace("\u2212", "-").replace("\u2013", "-")


def _check_trend_direction(
    clinician_notes: str,
    patient_narrative: str,
    badge: PatientTrendBadge,
    pac: float,
) -> str | None:
    """Memeriksa kesesuaian format PAC dan kata kunci arah tren; mengembalikan sub-alasan jika gagal."""
    c_low = clinician_notes.lower()
    p_low = patient_narrative.lower()
    combined = f"{c_low} {p_low}"

    # Format: narasi awam memakai nilai mutlak PAC (tidak boleh ada tanda minus di depan angka PAC)
    c_norm = _normalize_minus(clinician_notes).replace(",", ".")
    p_norm = _normalize_minus(patient_narrative).replace(",", ".")
    abs_pac = abs(pac)
    if abs_pac > 0:
        neg_candidates = [f"-{abs_pac:.2f}", f"-{abs_pac:.1f}"]
        if abs(abs_pac - round(abs_pac)) < 1e-6:
            neg_candidates.append(f"-{int(round(abs_pac))}")
        if any(fmt in p_norm for fmt in neg_candidates):
            return "pac_negatif_di_narasi_pasien"

    # Format: catatan klinis memakai tanda (+ atau -) untuk PAC jika PAC != 0
    if pac > 0:
        pos_candidates = [f"+{pac:.2f}", f"+{pac:.1f}"]
        if abs(pac - round(pac)) < 1e-6:
            pos_candidates.append(f"+{int(round(pac))}")
        if not any(s in c_norm for s in pos_candidates):
            return "pac_klinisi_tanpa_tanda_plus"
    elif pac < 0:
        min_candidates = [f"{pac:.2f}", f"{pac:.1f}"]
        if abs(pac - round(pac)) < 1e-6:
            min_candidates.append(f"{int(round(pac))}")
        if not any(s in c_norm for s in min_candidates):
            return "pac_klinisi_tanpa_tanda_minus"

    if badge == "menurun":
        has_shrink_cue = any(
            w in combined for w in ("menurun", "mengecil", "penurunan", "lebih kecil", "berkurang")
        )
        if not has_shrink_cue:
            return "kata_kunci_menurun_hilang"
        for w in ("meningkat", "membesar", "perluasan", "lebih besar", "bertambah"):
            if w in combined:
                return f"kata_berlawanan_pada_menurun:{w}"
        return None

    if badge == "meningkat":
        has_expand_cue = any(
            w in combined for w in ("meningkat", "membesar", "perluasan", "lebih besar", "bertambah")
        )
        if not has_expand_cue:
            return "kata_kunci_meningkat_hilang"
        for w in ("menurun", "mengecil", "penurunan", "lebih kecil", "berkurang"):
            if w in combined:
                return f"kata_berlawanan_pada_meningkat:{w}"
        return None

    if badge == "stabil":
        has_stable_cue = any(w in combined for w in ("stabil", "tidak berubah", "tidak terdeteksi perubahan"))
        if not has_stable_cue:
            return "kata_kunci_stabil_hilang"
        for w in (
            "area luka terukur menurun",
            "area luka terukur meningkat",
            "terdeteksi lebih kecil",
            "terdeteksi lebih besar",
            "perluasan luas",
            "penurunan luas",
        ):
            if w in combined:
                return f"kata_berlawanan_pada_stabil:{w}"
        return None

    return None


def _matches_trend_direction(
    clinician_notes: str,
    patient_narrative: str,
    badge: PatientTrendBadge,
    pac: float,
) -> bool:
    return _check_trend_direction(clinician_notes, patient_narrative, badge, pac) is None


_FOREIGN_UNIT_CM_RE = re.compile(r"\bcm(?:²|2)?\b|cm²", re.IGNORECASE)
_FOREIGN_UNIT_MM_RE = re.compile(r"\bmm(?:²|2)?\b|mm²", re.IGNORECASE)
_FOREIGN_UNIT_OTHER_RE = re.compile(r"\b(?:meter|inci|inch)\b", re.IGNORECASE)
_CM2_TOKEN_RE = re.compile(r"\bcm(?:²|2)\b|cm²", re.IGNORECASE)
_PCT_NUMBER_RE = re.compile(r"(?<![A-Za-z_])(\d+(?:[.,]\d+)?)\s*%")


def _check_unit_compliance(
    c_text: str,
    p_text: str,
    pac: float,
    unit: Literal["%", "cm²"],
) -> str | None:
    combined = f"{c_text} {p_text}"
    if _FOREIGN_UNIT_MM_RE.search(combined):
        return "satuan_asing:mm"
    if _FOREIGN_UNIT_OTHER_RE.search(combined):
        return "satuan_asing:meter_atau_inci"

    if unit == "%":
        if _FOREIGN_UNIT_CM_RE.search(combined):
            return "satuan_asing:cm"
        return None

    # unit == "cm²"
    if "poin persentase" in combined.lower():
        return "satuan_asing:poin_persentase"
    if not _CM2_TOKEN_RE.search(c_text):
        return "satuan_asing:tanpa_cm2"

    expected_abs_pac = abs(round(pac, 2))
    for match in _PCT_NUMBER_RE.finditer(combined):
        try:
            val = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if abs(val - expected_abs_pac) > NUMBER_ROUNDING_TOLERANCE:
            return f"satuan_asing:persen_pada_luas_cm2:{val}"

    return None


def validate_narrative_output(
    clinician_notes: str,
    patient_narrative: str,
    a0: float,
    at: float,
    delta_a: float,
    pac: float,
    badge: PatientTrendBadge,
    unit: Literal["%", "cm²"] = "%",
) -> tuple[bool, str]:
    """
    Memvalidasi keluaran narasi LLM terhadap aturan Tabel 3.4 & PRD v3 G8:
    1. Kedua narasi tidak kosong.
    2. Bebas kata terlarang (membaik, memburuk, sembuh, infeksi, diagnosis, resep).
    3. Kepatuhan satuan sesuai mode (unit="%" vs unit="cm²").
    4. Setiap angka di dalam teks wajib cocok dengan salah satu dari empat angka masukan
       (A0, A_t, |delta_A|, |PAC|) dalam toleransi pembulatan NUMBER_ROUNDING_TOLERANCE.
    5. Kedua narasi memuat disclaimer medis.
    6. Arah tren dan format tanda PAC sesuai dengan klasifikasi Tabel 3.3.
    """
    if not isinstance(clinician_notes, str) or not isinstance(patient_narrative, str):
        return False, "tipe_bukan_string"

    c_text = clinician_notes.strip()
    p_text = patient_narrative.strip()
    if not c_text or not p_text:
        return False, "narasi_kosong"

    for label, text in (("clinician_notes", c_text), ("patient_narrative", p_text)):
        bad_word = _contains_forbidden_word(text)
        if bad_word is not None:
            return False, f"kata_terlarang:{label}:{bad_word}"
        if not _has_required_disclaimer(text):
            return False, f"disclaimer_hilang:{label}"

    unit_err = _check_unit_compliance(c_text, p_text, pac, unit)
    if unit_err is not None:
        return False, unit_err

    allowed_magnitudes = (
        abs(round(a0, 2)),
        abs(round(at, 2)),
        abs(round(delta_a, 2)),
        abs(round(pac, 2)),
    )
    extracted_numbers = extract_numbers_from_text(c_text) + extract_numbers_from_text(p_text)
    if not extracted_numbers:
        return False, "tidak_ada_angka"

    for num in extracted_numbers:
        if not any(abs(num - target) <= NUMBER_ROUNDING_TOLERANCE for target in allowed_magnitudes):
            return False, f"angka_asing:{num}"

    trend_err = _check_trend_direction(c_text, p_text, badge, pac)
    if trend_err is not None:
        return False, f"arah_tren_atau_format_pac_tidak_sesuai:{trend_err}"

    if badge == "meningkat" and not _has_meningkat_consultation_call(p_text):
        return False, "ajakan_konsultasi_hilang:patient_narrative"

    return True, "ok"


def _fmt_dec(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _fmt_signed_dec(value: float) -> str:
    return f"{value:+.2f}".replace(".", ",")


def generate_fallback_narrative(
    a0: float,
    at: float,
    delta_a: float,
    pac: float | None,
    badge: PatientTrendBadge,
    unit: Literal["%", "cm²"] = "%",
) -> tuple[str, str, str]:
    """
    Templat narasi deterministik sesuai Tabel 3.5 (Bab 3.8) & PRD v3 G8 (mode % atau cm²).
    Mengembalikan tuple: (clinician_notes, patient_narrative, narrative_source).
    """
    is_cm2 = unit == "cm²"
    satuan = " cm²" if is_cm2 else "%"
    satuan_delta = " cm²" if is_cm2 else " poin persentase"
    a0_s = _fmt_dec(a0)
    at_s = _fmt_dec(at)
    delta_s = _fmt_signed_dec(delta_a)
    frasa_area_pasien = f"{at_s} cm²" if is_cm2 else f"{at_s}% dari area foto"

    if pac is None or badge == "tidak_dapat_dihitung":
        clinician_notes = (
            f"Evaluasi Longitudinal (T₁ → Tₜ): Luas luka awal tercatat {a0_s}{satuan} dan luas saat ini "
            f"{at_s}{satuan} (ΔA: {delta_s}{satuan_delta}, PAC tidak dapat dihitung karena A₀ = 0). "
            "Pemeriksaan klinis langsung tetap diperlukan karena hasil merupakan estimasi berdasarkan foto."
        )
        patient_narrative = (
            f"Berdasarkan hasil pengukuran sistem, luas area luka saat ini terdeteksi sekitar {frasa_area_pasien}. "
            "Tetap konsultasikan kondisi luka kepada perawat atau dokter. "
            "Hasil ini merupakan estimasi berdasarkan foto, bukan diagnosis medis."
        )
        return clinician_notes, patient_narrative, "template_fallback"

    pac_s = _fmt_dec(pac)
    pac_signed_s = _fmt_signed_dec(pac)
    abs_pac_s = _fmt_dec(abs(pac))

    if badge == "menurun":
        clinician_notes = (
            f"Evaluasi Longitudinal (T₁ → Tₜ): Area luka terukur menurun dari {a0_s}{satuan} menjadi "
            f"{at_s}{satuan} (PAC: +{pac_s}%, ΔA: {delta_s}{satuan_delta}). Hasil pengukuran "
            "menunjukkan penurunan luas permukaan luka. Pemeriksaan klinis langsung tetap diperlukan "
            "karena hasil merupakan estimasi berdasarkan foto."
        )
        patient_narrative = (
            f"Berdasarkan hasil pengukuran sistem, area luka pada pemeriksaan ini terdeteksi lebih "
            f"kecil dibandingkan pemeriksaan sebelumnya (berkurang sekitar {abs_pac_s}%). Tetap lanjutkan "
            "perawatan sesuai anjuran perawat atau dokter. Hasil ini merupakan estimasi berdasarkan "
            "foto, bukan diagnosis medis."
        )
        return clinician_notes, patient_narrative, "template_fallback"

    if badge == "meningkat":
        clinician_notes = (
            f"Evaluasi Longitudinal (T₁ → Tₜ): Area luka terukur meningkat dari {a0_s}{satuan} menjadi "
            f"{at_s}{satuan} (PAC: {pac_s}%, ΔA: {delta_s}{satuan_delta}). Hasil pengukuran "
            "menunjukkan perluasan luas permukaan luka. Pemeriksaan klinis langsung diperlukan untuk "
            "menentukan tindakan selanjutnya karena hasil merupakan estimasi berdasarkan foto."
        )
        patient_narrative = (
            f"Berdasarkan hasil pengukuran sistem, area luka pada pemeriksaan ini terdeteksi lebih "
            f"besar dibandingkan pemeriksaan sebelumnya (bertambah sekitar {abs_pac_s}%). Segera "
            "konsultasikan hasil ini kepada perawat atau dokter untuk pemeriksaan lebih lanjut. "
            "Hasil ini merupakan estimasi berdasarkan foto, bukan diagnosis medis."
        )
        return clinician_notes, patient_narrative, "template_fallback"

    # Default: Tren Stabil (Perubahan Minimal)
    clinician_notes = (
        f"Evaluasi Longitudinal (T₁ → Tₜ): Tidak terdeteksi perubahan berarti pada luas luka "
        f"({a0_s}{satuan} → {at_s}{satuan}, ΔA: {delta_s}{satuan_delta}, PAC: {pac_signed_s}%). "
        "Hasil pengukuran menunjukkan luas luka relatif stabil. Pemeriksaan klinis langsung "
        "tetap diperlukan karena hasil merupakan estimasi berdasarkan foto."
    )
    patient_narrative = (
        f"Berdasarkan hasil pengukuran sistem, area luka relatif tidak berubah dibandingkan "
        f"pemeriksaan sebelumnya, dengan luas sekitar {frasa_area_pasien}. Tetap konsultasikan "
        "kondisi luka kepada perawat atau dokter. Hasil ini merupakan estimasi berdasarkan foto, "
        "bukan diagnosis medis."
    )
    return clinician_notes, patient_narrative, "template_fallback"


async def request_gemini_api(
    user_payload: dict[str, float | str],
    *,
    api_key: str,
    model: str,
    timeout_seconds: float,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> dict[str, object]:
    """
    Memanggil endpoint REST Google Gemini API (generateContent) secara asinkron
    menggunakan header x-goog-api-key (agar API key tidak pernah muncul di URL log).
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    effective_temperature = (
        settings.gemini_temperature if temperature is None else temperature
    )
    effective_max_tokens = (
        settings.gemini_max_output_tokens if max_output_tokens is None else max_output_tokens
    )
    generation_config: dict[str, object] = {
        "temperature": effective_temperature,
        "maxOutputTokens": effective_max_tokens,
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT",
            "properties": {
                "clinician_notes": {"type": "STRING"},
                "patient_narrative": {"type": "STRING"},
            },
            "required": ["clinician_notes", "patient_narrative"],
        },
    }
    if any(ver in model for ver in ("2.5", "3.")):
        generation_config["thinkingConfig"] = {"thinkingBudget": 0}

    request_body = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT_TABEL_3_4}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": json.dumps(user_payload, ensure_ascii=False)}],
            }
        ],
        "generationConfig": generation_config,
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=request_body, headers=headers)
        response.raise_for_status()
        return response.json()


_LOG_CONTROL_CHARS_RE = re.compile(r"[\r\n\t]+")
_LOG_PII_PATTERNS = (
    re.compile(r"\bRM[-\s]?\d+\b", re.IGNORECASE),
    re.compile(r"\bPatient_[A-Za-z0-9_]+\b", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b(?:Tn|Ny|Nn|An|Sdr|Bapak|Ibu)\.?\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b"),
    re.compile(r"\b(?:\+?\d[\d\s-]{5,}\d|\d{6,})\b"),
)


def _sanitize_narrative_for_log(text: str) -> str:
    """Membersihkan baris baru/karakter kontrol serta menyamarkan pola PII sebelum dicatat ke log."""
    cleaned = _LOG_CONTROL_CHARS_RE.sub(" ", text).strip()
    for pat in _LOG_PII_PATTERNS:
        cleaned = pat.sub("[REDACTED_PII]", cleaned)
    return cleaned


def _extract_json_from_gemini_response(raw_response: dict[str, object]) -> dict[str, str]:
    candidates = raw_response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Respons Gemini tidak memiliki candidates.")
    first = candidates[0]
    if not isinstance(first, dict):
        raise ValueError("Format candidate Gemini tidak valid.")
    content = first.get("content")
    if not isinstance(content, dict):
        raise ValueError("Format content Gemini tidak valid.")
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], dict):
        raise ValueError("Format parts Gemini tidak valid.")
    text_val = parts[0].get("text")
    if not isinstance(text_val, str) or not text_val.strip():
        raise ValueError("Teks keluaran Gemini kosong.")
    parsed = json.loads(text_val)
    if not isinstance(parsed, dict):
        raise ValueError("Keluaran Gemini bukan objek JSON.")
    return {
        "clinician_notes": str(parsed.get("clinician_notes", "")),
        "patient_narrative": str(parsed.get("patient_narrative", "")),
    }


async def generate_longitudinal_narrative(
    a0: float,
    at: float,
    delta_a: float,
    pac: float | None,
    badge: PatientTrendBadge,
    trend_status: str,
    unit: Literal["%", "cm²"] = "%",
) -> tuple[str, str, str]:
    """
    Menghasilkan narasi ganda untuk kunjungan lanjutan (t >= 2):
    - Jika A0 <= 0 atau PAC None: langsung gunakan fallback tanpa memanggil Gemini.
    - Jika GEMINI_API_KEY kosong: gunakan fallback.
    - Panggil Gemini (timeout 10 detik), validasi JSON dan aturan Tabel 3.4 / PRD v3 G8.
    - Jika gagal/timeout/JSON rusak/ditolak validator: gunakan templat Tabel 3.5 (template_fallback).
    """
    if pac is None or badge == "tidak_dapat_dihitung" or a0 <= 0.0:
        return generate_fallback_narrative(
            a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge, unit=unit
        )

    api_key = settings.gemini_api_key.strip()
    if not api_key:
        logger.warning("Narrative fallback reason=no_api_key")
        return generate_fallback_narrative(
            a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge, unit=unit
        )

    user_payload = build_gemini_user_prompt(
        a0=a0,
        at=at,
        delta_a=delta_a,
        pac=pac,
        trend_status=trend_status,
        unit=unit,
    )

    try:
        raw_resp = await request_gemini_api(
            user_payload=user_payload,
            api_key=api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
            temperature=settings.gemini_temperature,
            max_output_tokens=settings.gemini_max_output_tokens,
        )
    except (httpx.TimeoutException, TimeoutError):
        logger.warning("Narrative fallback reason=timeout")
        return generate_fallback_narrative(
            a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge, unit=unit
        )
    except httpx.HTTPStatusError as exc:
        logger.warning("Narrative fallback reason=http_error:%s", exc.response.status_code)
        return generate_fallback_narrative(
            a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge, unit=unit
        )
    except Exception:
        logger.warning("Narrative fallback reason=http_error:network")
        return generate_fallback_narrative(
            a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge, unit=unit
        )

    try:
        parsed = _extract_json_from_gemini_response(raw_resp)
    except (ValueError, json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Narrative fallback reason=invalid_json")
        return generate_fallback_narrative(
            a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge, unit=unit
        )

    is_valid, reason = validate_narrative_output(
        clinician_notes=parsed["clinician_notes"],
        patient_narrative=parsed["patient_narrative"],
        a0=a0,
        at=at,
        delta_a=delta_a,
        pac=pac,
        badge=badge,
        unit=unit,
    )
    if not is_valid:
        logger.warning(
            "Narrative fallback reason=validator_rejected:%s raw_clinician_notes=%r raw_patient_narrative=%r",
            reason,
            _sanitize_narrative_for_log(parsed["clinician_notes"]),
            _sanitize_narrative_for_log(parsed["patient_narrative"]),
        )
        return generate_fallback_narrative(
            a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge, unit=unit
        )

    return parsed["clinician_notes"].strip(), parsed["patient_narrative"].strip(), "llm"


def get_narrative_service() -> NarrativeServiceFn:
    return generate_longitudinal_narrative
