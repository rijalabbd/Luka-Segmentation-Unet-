from collections.abc import Callable, Coroutine
import json
import logging
import re
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.schemas.patient import PatientTrendBadge

logger = logging.getLogger("woundai.narrative")

FORBIDDEN_WORDS: tuple[str, ...] = (
    "membaik",
    "memburuk",
    "sembuh",
    "infeksi",
    "diagnosis",
    "resep",
)

SYSTEM_PROMPT_TABEL_3_4: str = (
    "Anda adalah asisten dokumentasi pemantauan luka kusta (WoundAI) yang menganalisis perubahan "
    "luas area luka secara longitudinal.\n"
    "Patuhi 6 aturan ketat berikut tanpa pengecualian:\n"
    "1. Kepatuhan Angka: Gunakan angka sesuai data masukan (A0, At, delta_A, PAC) tanpa mengubah, "
    "membulatkan sembarangan, atau menambahkan angka baru.\n"
    "2. Larangan Diagnosis: Dilarang memberikan diagnosis medis maupun meresepkan obat/terapi spesifik. "
    "Dilarang memakai kata: membaik, memburuk, sembuh, infeksi, diagnosis, resep.\n"
    "3. Bahasa Observasional: Gunakan istilah pengamatan fisik (\"terdeteksi mengecil\", \"terukur membesar\", \"relatif stabil\").\n"
    "4. Disclaimer Medis: Wajib menyertakan keterangan bahwa hasil merupakan estimasi visual sistem berdasarkan foto "
    "dan memerlukan pemeriksaan langsung oleh tenaga medis.\n"
    "5. Narasi Pasien (patient_narrative): Bahasa Indonesia sehari-hari yang sederhana, empatik, dan mudah dipahami awam. "
    "Gunakan nilai mutlak PAC (misalnya \"berkurang sekitar 21.05%\" atau \"bertambah sekitar 15.20%\").\n"
    "6. Catatan Klinisi (clinician_notes): Bahasa medis formal dan ringkas dengan mencantumkan nilai A0, At, delta_A, "
    "dan PAC dengan tanda (+ atau -).\n\n"
    "Format keluaran WAJIB berupa JSON dengan persis 2 kunci string:\n"
    "{\n"
    '  "clinician_notes": "...",\n'
    '  "patient_narrative": "..."\n'
    "}"
)


def build_gemini_user_prompt(
    a0: float,
    at: float,
    delta_a: float,
    pac: float,
    trend_status: str,
) -> str:
    """
    User prompt strictly limited to 5 numbers and status label.
    Contains no patient PII (no name, no RM code, no age, no images).
    """
    return (
        f"A0: {a0:.2f}%\n"
        f"At: {at:.2f}%\n"
        f"delta_A: {delta_a:+.2f}%\n"
        f"PAC: {pac:+.2f}%\n"
        f"trend_status: {trend_status}"
    )


def extract_numbers_from_text(text: str) -> list[float]:
    """Ekstraksi seluruh token angka bertanda atau desimal (titik atau koma)."""
    raw_tokens = re.findall(r"[-+]?\d+(?:[.,]\d+)?", text)
    numbers: list[float] = []
    for token in raw_tokens:
        clean = token.replace(",", ".")
        try:
            numbers.append(float(clean))
        except ValueError:
            continue
    return numbers


def validate_narrative_text(
    clinician_notes: str,
    patient_narrative: str,
    a0: float,
    at: float,
    delta_a: float,
    pac: float,
    badge: PatientTrendBadge,
) -> tuple[bool, str]:
    """
    Validasi ketat terhadap narasi yang dihasilkan LLM:
    1. Tidak boleh mengandung kata-kata terlarang (Tabel 3.4 Aturan 2).
    2. Wajib menyertakan disclaimer medis (Tabel 3.4 Aturan 4).
    3. Seluruh angka harus bersumber dari 5 angka masukan (toleransi ±0.15) atau integer indeks kecil.
    4. Arah tren pada narasi pasien tidak boleh terbalik.
    """
    combined_lower = f"{clinician_notes} {patient_narrative}".lower()

    # 1. Cek kata terlarang
    for word in FORBIDDEN_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", combined_lower):
            return False, f"Kata terlarang terdeteksi: '{word}'"

    # 2. Cek disclaimer medis pada kedua teks
    c_lower = clinician_notes.lower()
    p_lower = patient_narrative.lower()
    has_c_disclaimer = "estimasi" in c_lower and ("pemeriksaan" in c_lower or "tenaga medis" in c_lower or "dokter" in c_lower or "klinis" in c_lower)
    has_p_disclaimer = "estimasi" in p_lower and ("pemeriksaan" in p_lower or "tenaga medis" in p_lower or "dokter" in p_lower or "perawat" in p_lower or "klinis" in p_lower)
    if not (has_c_disclaimer and has_p_disclaimer):
        return False, "Disclaimer medis estimasi visual tidak lengkap pada narasi klinisi atau pasien."

    # 3. Cek angka asing (K8)
    allowed_base = [
        abs(a0),
        abs(at),
        abs(delta_a),
        abs(pac),
        a0,
        at,
        delta_a,
        pac,
    ]
    # Small integers allowed for visit numbering (e.g. T1, T2, kunjungan ke-1)
    allowed_small_ints = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0}

    for text_to_check in (clinician_notes, patient_narrative):
        nums = extract_numbers_from_text(text_to_check)
        for num in nums:
            # Check if num is close to any allowed base parameter
            matches_base = any(abs(num - allowed) < 0.15 or abs(abs(num) - abs(allowed)) < 0.15 for allowed in allowed_base)
            if matches_base:
                continue
            if num in allowed_small_ints:
                continue
            return False, f"Angka asing ({num}) tidak cocok dengan parameter masukan."

    # 4. Cek konsistensi arah tren
    if badge == "menurun":
        if "membesar" in p_lower or "bertambah" in p_lower:
            return False, "Arah tren terbalik: status menurun tetapi narasi menyebut membesar/bertambah."
    elif badge == "meningkat":
        if "mengecil" in p_lower or "berkurang" in p_lower:
            return False, "Arah tren terbalik: status meningkat tetapi narasi menyebut mengecil/berkurang."

    return True, "Valid"


def generate_fallback_narrative(
    a0: float,
    at: float,
    delta_a: float,
    pac: float | None,
    badge: PatientTrendBadge,
) -> tuple[str, str, Literal["template_fallback"]]:
    """
    Templat narasi deterministik persis sesuai Tabel 3.5 (Bab 3.8).
    Mengembalikan tuple: (clinician_notes, patient_narrative, 'template_fallback').
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
    user_prompt: str,
    api_key: str,
    model: str = "gemini-2.0-flash",
    timeout_seconds: float = 10.0,
) -> dict[str, Any] | None:
    """
    Mengirim permintaan asinkron ke Google Gemini API via REST dengan structured JSON output.
    Menggunakan header x-goog-api-key untuk menjaga keamanan API key agar tidak tercatat di URL query log.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT_TABEL_3_4}]
        },
        "contents": [
            {"parts": [{"text": user_prompt}]}
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

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.warning(
                    "Gemini API mengembalikan status HTTP %s: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return None
            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                logger.warning("Gemini API tidak mengembalikan kandidat respon.")
                return None
            text_out = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return json.loads(text_out)
    except httpx.TimeoutException:
        logger.warning("Gemini API timeout (>%.1fs). Segera beralih ke templat fallback.", timeout_seconds)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini API gagal (%s: %s). Segera beralih ke templat fallback.", type(exc).__name__, exc)
        return None


async def generate_longitudinal_narrative(
    a0: float,
    at: float,
    delta_a: float,
    pac: float | None,
    trend_status: str | None,
    badge: PatientTrendBadge,
    api_key: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 10.0,
) -> tuple[str, str, Literal["llm", "template_fallback"]]:
    """
    Fungsi orkestrasi narasi longitudinal:
    - Jika PAC tidak dapat dihitung atau A0 == 0: langsung pakai fallback deterministik.
    - Coba panggil Gemini jika API key tersedia.
    - Jalankan validasi angka, kata terlarang, dan disclaimer.
    - Jika gagal pada tahap apapun, kembalikan templat Tabel 3.5 (template_fallback).
    """
    if pac is None or a0 == 0 or badge == "tidak_dapat_dihitung" or not trend_status:
        return generate_fallback_narrative(a0, at, delta_a, pac, badge)

    key = api_key or settings.gemini_api_key
    mdl = model or settings.gemini_model or "gemini-2.0-flash"

    if not key:
        logger.info("GEMINI_API_KEY kosong. Menggunakan templat deterministik Tabel 3.5.")
        return generate_fallback_narrative(a0, at, delta_a, pac, badge)

    prompt = build_gemini_user_prompt(a0, at, delta_a, pac, trend_status)
    parsed_json = await request_gemini_api(prompt, key, mdl, timeout_seconds)

    if not isinstance(parsed_json, dict):
        return generate_fallback_narrative(a0, at, delta_a, pac, badge)

    c_notes = str(parsed_json.get("clinician_notes") or "").strip()
    p_narrative = str(parsed_json.get("patient_narrative") or "").strip()

    if not c_notes or not p_narrative:
        return generate_fallback_narrative(a0, at, delta_a, pac, badge)

    is_valid, reason = validate_narrative_text(c_notes, p_narrative, a0, at, delta_a, pac, badge)
    if not is_valid:
        logger.warning("Validasi narasi Gemini gagal (%s). Beralih ke fallback Tabel 3.5.", reason)
        return generate_fallback_narrative(a0, at, delta_a, pac, badge)

    return c_notes, p_narrative, "llm"


NarrativeFn = Callable[
    [float, float, float, float | None, str | None, PatientTrendBadge],
    Coroutine[Any, Any, tuple[str, str, Literal["llm", "template_fallback"]]],
]


def get_narrative_service() -> NarrativeFn:
    """Dependency provider untuk FastAPI endpoint /visits/{id}/confirm."""
    async def _service(
        a0: float,
        at: float,
        delta_a: float,
        pac: float | None,
        trend_status: str | None,
        badge: PatientTrendBadge,
    ) -> tuple[str, str, Literal["llm", "template_fallback"]]:
        return await generate_longitudinal_narrative(
            a0=a0,
            at=at,
            delta_a=delta_a,
            pac=pac,
            trend_status=trend_status,
            badge=badge,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
        )

    return _service
