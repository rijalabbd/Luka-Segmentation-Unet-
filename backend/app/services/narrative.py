from app.schemas.patient import PatientTrendBadge


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

