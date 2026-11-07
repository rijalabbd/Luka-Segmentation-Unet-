from collections.abc import Awaitable, Callable
import json
import logging
import re

import httpx

from app.core.config import settings
from app.schemas.patient import PatientTrendBadge

logger = logging.getLogger(__name__)

# Enam aturan system prompt sesuai Tabel 3.4 proposal (Bab 3.8)
SYSTEM_PROMPT_TABEL_3_4 = """Anda adalah asisten dokumentasi klinis untuk pemantauan longitudinal ulkus kusta.
Hasilkan keluaran HANYA dalam format JSON valid dengan tepat dua kunci: "clinician_notes" dan "patient_narrative".
Wajib patuhi enam aturan berikut tanpa pengecualian:
1. Kepatuhan Angka: Gunakan angka sesuai data masukan (A0, A_t, delta_A, PAC) tanpa mengubah, membulatkan sembarangan, atau menambahkan angka baru apa pun di luar data masukan.
2. Larangan Diagnosis: Dilarang memberikan diagnosis medis maupun meresepkan obat atau terapi spesifik.
3. Bahasa Observasional: Gunakan istilah pengamatan fisik ("terdeteksi mengecil", "terukur membesar", "relatif stabil"). Dilarang keras memakai kata "membaik", "memburuk", "sembuh", "infeksi", "diagnosis", atau "resep".
4. Disclaimer Medis: Wajib menyertakan keterangan di kedua narasi bahwa hasil merupakan estimasi visual berdasarkan foto dan memerlukan pemeriksaan klinis langsung oleh tenaga medis (perawat atau dokter), serta bukan diagnosis medis.
5. Narasi Pasien ("patient_narrative"): Gunakan bahasa Indonesia sehari-hari yang sederhana, empatik, mudah dipahami awam, dan cantumkan nilai mutlak PAC (tanpa tanda negatif '-').
6. Catatan Klinisi ("clinician_notes"): Gunakan bahasa medis formal dan ringkas dengan mencantumkan keempat nilai A0, A_t, delta_A (dengan tanda + atau -), dan PAC (dengan tanda + atau -)."""

FORBIDDEN_WORDS = (
    "membaik",
    "memburuk",
    "sembuh",
    "infeksi",
    "diagnosis",
    "resep",
)

# Toleransi pembulatan angka (mis. 21.05% vs 21.1% berselisih 0.05 <= 0.15)
NUMBER_ROUNDING_TOLERANCE = 0.15

NarrativeServiceFn = Callable[
    [float, float, float, float | None, PatientTrendBadge, str],
    Awaitable[tuple[str, str, str]],
]


def build_gemini_user_prompt(
    a0: float,
    at: float,
    delta_a: float,
    pac: float,
    trend_status: str,
) -> dict[str, float | str]:
    """
    Membuat muatan user prompt ke Gemini yang HANYA berisi lima field:
    A0, A_t, delta_A, PAC, dan status tren (tanpa PII, nama, kode RM, atau citra).
    """
    return {
        "A0": round(a0, 2),
        "A_t": round(at, 2),
        "delta_A": round(delta_a, 2),
        "PAC": round(pac, 2),
        "trend_status": trend_status,
    }


def extract_numbers_from_text(text: str) -> list[float]:
    """
    Mengekstrak seluruh angka (integer maupun desimal dengan titik atau koma) dari teks,
    setelah mengabaikan token notasi indeks tetap seperti 'T₁' atau 'T1'.
    """
    cleaned = re.sub(r"\bT[₁1]\b", "T_awal", text)
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
    # Izinkan frasa disclaimer resmi "bukan diagnosis medis" / "bukanlah diagnosis medis"
    sanitized = re.sub(r"\bbukan(?:lah)?\s+diagnosis(?:\s+medis)?\b", "", lowered)
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


def _matches_trend_direction(
    clinician_notes: str,
    patient_narrative: str,
    badge: PatientTrendBadge,
    pac: float,
) -> bool:
    c_low = clinician_notes.lower()
    p_low = patient_narrative.lower()
    combined = f"{c_low} {p_low}"

    # Format: narasi awam memakai nilai mutlak PAC (tidak boleh ada tanda minus di depan angka PAC)
    abs_pac = abs(pac)
    if abs_pac > 0:
        for fmt in (f"-{abs_pac:.2f}", f"-{abs_pac:.1f}", f"-{abs_pac:.2f}".replace(".", ","), f"-{abs_pac:.1f}".replace(".", ",")):
            if fmt in patient_narrative:
                return False

    # Format: catatan klinis memakai tanda (+ atau -) untuk PAC jika PAC != 0
    if pac > 0:
        has_plus = any(
            s in clinician_notes
            for s in (
                f"+{pac:.2f}",
                f"+{pac:.1f}",
                f"+{pac:.2f}".replace(".", ","),
                f"+{pac:.1f}".replace(".", ","),
            )
        )
        if not has_plus:
            return False
    elif pac < 0:
        has_minus = any(
            s in clinician_notes
            for s in (
                f"{pac:.2f}",
                f"{pac:.1f}",
                f"{pac:.2f}".replace(".", ","),
                f"{pac:.1f}".replace(".", ","),
            )
        )
        if not has_minus:
            return False

    if badge == "menurun":
        has_shrink_cue = any(
            w in combined for w in ("menurun", "mengecil", "penurunan", "lebih kecil", "berkurang")
        )
        has_opposite = any(
            w in combined for w in ("meningkat", "membesar", "perluasan", "lebih besar", "bertambah")
        )
        return has_shrink_cue and not has_opposite

    if badge == "meningkat":
        has_expand_cue = any(
            w in combined for w in ("meningkat", "membesar", "perluasan", "lebih besar", "bertambah")
        )
        has_opposite = any(
            w in combined for w in ("menurun", "mengecil", "penurunan", "lebih kecil", "berkurang")
        )
        return has_expand_cue and not has_opposite

    if badge == "stabil":
        has_stable_cue = any(w in combined for w in ("stabil", "tidak berubah", "tidak terdeteksi perubahan"))
        has_opposite = any(
            w in combined
            for w in (
                "area luka terukur menurun",
                "area luka terukur meningkat",
                "terdeteksi lebih kecil",
                "terdeteksi lebih besar",
                "perluasan luas",
                "penurunan luas",
            )
        )
        return has_stable_cue and not has_opposite

    return True


def validate_narrative_output(
    clinician_notes: str,
    patient_narrative: str,
    a0: float,
    at: float,
    delta_a: float,
    pac: float,
    badge: PatientTrendBadge,
) -> tuple[bool, str]:
    """
    Memvalidasi keluaran narasi LLM terhadap aturan Tabel 3.4:
    1. Kedua narasi tidak kosong.
    2. Bebas kata terlarang (membaik, memburuk, sembuh, infeksi, diagnosis, resep).
    3. Setiap angka di dalam teks wajib cocok dengan salah satu dari empat angka masukan
       (A0, A_t, |delta_A|, |PAC|) dalam toleransi pembulatan NUMBER_ROUNDING_TOLERANCE.
    4. Kedua narasi memuat disclaimer medis.
    5. Arah tren dan format tanda PAC sesuai dengan klasifikasi Tabel 3.3.
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

    if not _matches_trend_direction(c_text, p_text, badge, pac):
        return False, "arah_tren_atau_format_pac_tidak_sesuai"

    return True, "ok"


def generate_fallback_narrative(
    a0: float,
    at: float,
    delta_a: float,
    pac: float | None,
    badge: PatientTrendBadge,
) -> tuple[str, str, str]:
    """
    Templat narasi deterministik sesuai Tabel 3.5 (Bab 3.8).
    Mengembalikan tuple: (clinician_notes, patient_narrative, narrative_source).
    """
    if pac is None or badge == "tidak_dapat_dihitung":
        clinician_notes = (
            f"Evaluasi Longitudinal (T₁ → Tₜ): Luas luka awal tercatat {a0:.2f}% dan luas saat ini "
            f"{at:.2f}% (ΔA: {delta_a:+.2f} poin persentase, PAC tidak dapat dihitung karena A₀ = 0). "
            "Pemeriksaan klinis langsung tetap diperlukan karena hasil merupakan estimasi berdasarkan foto."
        )
        patient_narrative = (
            f"Berdasarkan hasil pengukuran sistem, luas area luka saat ini terdeteksi sekitar {at:.2f}% "
            "dari area foto. Tetap konsultasikan kondisi luka kepada perawat atau dokter. "
            "Hasil ini merupakan estimasi berdasarkan foto, bukan diagnosis medis."
        )
        return clinician_notes, patient_narrative, "template_fallback"

    if badge == "menurun":
        clinician_notes = (
            f"Evaluasi Longitudinal (T₁ → Tₜ): Area luka terukur menurun dari {a0:.2f}% menjadi "
            f"{at:.2f}% (PAC: +{pac:.2f}%, ΔA: {delta_a:+.2f} poin persentase). Hasil pengukuran "
            "menunjukkan penurunan luas permukaan luka. Pemeriksaan klinis langsung tetap diperlukan "
            "karena hasil merupakan estimasi berdasarkan foto."
        )
        patient_narrative = (
            f"Berdasarkan hasil pengukuran sistem, area luka pada pemeriksaan ini terdeteksi lebih "
            f"kecil dibandingkan pemeriksaan sebelumnya (berkurang sekitar {pac:.2f}%). Tetap lanjutkan "
            "perawatan sesuai anjuran perawat atau dokter. Hasil ini merupakan estimasi berdasarkan "
            "foto, bukan diagnosis medis."
        )
        return clinician_notes, patient_narrative, "template_fallback"

    if badge == "meningkat":
        abs_pac = abs(pac)
        clinician_notes = (
            f"Evaluasi Longitudinal (T₁ → Tₜ): Area luka terukur meningkat dari {a0:.2f}% menjadi "
            f"{at:.2f}% (PAC: {pac:.2f}%, ΔA: {delta_a:+.2f} poin persentase). Hasil pengukuran "
            "menunjukkan perluasan luas permukaan luka. Pemeriksaan klinis langsung diperlukan untuk "
            "menentukan tindakan selanjutnya."
        )
        patient_narrative = (
            f"Berdasarkan hasil pengukuran sistem, area luka pada pemeriksaan ini terdeteksi lebih "
            f"besar dibandingkan pemeriksaan sebelumnya (bertambah sekitar {abs_pac:.2f}%). Segera "
            "konsultasikan hasil ini kepada perawat atau dokter untuk pemeriksaan lebih lanjut. "
            "Hasil ini merupakan estimasi berdasarkan foto, bukan diagnosis medis."
        )
        return clinician_notes, patient_narrative, "template_fallback"

    # Default: Tren Stabil (Perubahan Minimal)
    clinician_notes = (
        f"Evaluasi Longitudinal (T₁ → Tₜ): Tidak terdeteksi perubahan berarti pada luas luka "
        f"({a0:.2f}% → {at:.2f}%, ΔA: {delta_a:+.2f} poin persentase, PAC: {pac:+.2f}%). "
        "Hasil pengukuran menunjukkan luas luka relatif stabil. Pemeriksaan klinis langsung "
        "tetap diperlukan."
    )
    patient_narrative = (
        f"Berdasarkan hasil pengukuran sistem, area luka relatif tidak berubah dibandingkan "
        f"pemeriksaan sebelumnya, dengan luas sekitar {at:.2f}% dari area foto. Tetap konsultasikan "
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
) -> dict[str, object]:
    """
    Memanggil endpoint REST Google Gemini API (generateContent) secara asinkron
    menggunakan header x-goog-api-key (agar API key tidak pernah muncul di URL log).
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
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
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 800,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "clinician_notes": {"type": "STRING"},
                    "patient_narrative": {"type": "STRING"},
                },
                "required": ["clinician_notes", "patient_narrative"],
            },
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=request_body, headers=headers)
        response.raise_for_status()
        return response.json()


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
) -> tuple[str, str, str]:
    """
    Menghasilkan narasi ganda untuk kunjungan lanjutan (t >= 2):
    - Jika A0 <= 0 atau PAC None: langsung gunakan fallback tanpa memanggil Gemini.
    - Jika GEMINI_API_KEY kosong: gunakan fallback.
    - Panggil Gemini (timeout 10 detik), validasi JSON dan aturan Tabel 3.4.
    - Jika gagal/timeout/JSON rusak/ditolak validator: gunakan templat Tabel 3.5 (template_fallback).
    """
    if pac is None or badge == "tidak_dapat_dihitung" or a0 <= 0.0:
        return generate_fallback_narrative(a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge)

    api_key = settings.gemini_api_key.strip()
    if not api_key:
        return generate_fallback_narrative(a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge)

    user_payload = build_gemini_user_prompt(
        a0=a0,
        at=at,
        delta_a=delta_a,
        pac=pac,
        trend_status=trend_status,
    )

    try:
        raw_resp = await request_gemini_api(
            user_payload,
            api_key=api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
        )
        parsed = _extract_json_from_gemini_response(raw_resp)
    except Exception as exc:
        logger.warning(
            "Panggilan Gemini gagal (%s); beralih ke template_fallback.",
            type(exc).__name__,
        )
        return generate_fallback_narrative(a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge)

    is_valid, reason = validate_narrative_output(
        clinician_notes=parsed["clinician_notes"],
        patient_narrative=parsed["patient_narrative"],
        a0=a0,
        at=at,
        delta_a=delta_a,
        pac=pac,
        badge=badge,
    )
    if not is_valid:
        logger.warning("Narasi Gemini ditolak validator (%s); beralih ke template_fallback.", reason)
        return generate_fallback_narrative(a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge)

    return parsed["clinician_notes"].strip(), parsed["patient_narrative"].strip(), "llm"


def get_narrative_service() -> NarrativeServiceFn:
    return generate_longitudinal_narrative
