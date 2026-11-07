"""
Skrip seeding data uji H3 (Bagian 10 PRD):
- Membuat pasien demo RM-0010 (is_demo=True) dengan 2 kunjungan final berisi citra asli
  dari ml/test_set/Images/Patient_10/ (P10T_1.jpg dan P10T_2.jpg) lewat endpoint aplikasi
  (POST /api/v1/patients -> POST /api/v1/patients/{id}/visits -> POST /api/v1/visits/{id}/confirm).
- Menyiapkan pasien demo RM-0024 (is_demo=True, 0 kunjungan final -> untuk uji Kunjungan 1 / baseline),
  serta memastikan pasien demo RM-0012 (kunjungan tanpa citra) dan RM-0023 (1 kunjungan) tersedia.
- Dapat dibersihkan kembali dengan argumen `--clear`.
"""
import argparse
import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app.core.database import AsyncSessionLocal
from app.main import app
from app.services.segmentation import get_loaded_model, load_segmentation_model
from app.services.seed import seed_demo_patients


def _find_test_image(rel_path: str) -> Path:
    candidates = [
        Path("/app/ml/test_set") / rel_path,
        Path("ml/test_set") / rel_path,
        Path("../ml/test_set") / rel_path,
    ]
    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError(f"Citra uji tidak ditemukan: {rel_path}")


async def seed_h3_test_data(clear: bool = False) -> None:
    if get_loaded_model() is None:
        load_segmentation_model()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        if clear:
            for pid in ("RM-0010", "RM-0016", "RM-0024"):
                res = await client.delete(f"/api/v1/patients/{pid}")
                if res.status_code == 200:
                    print(f"[CLEAR] Pasien {pid} beserta berkas citranya dihapus.")
                else:
                    print(f"[CLEAR] Pasien {pid} tidak ada (HTTP {res.status_code}).")
            return

        async with AsyncSessionLocal() as session:
            await seed_demo_patients(session)

        # Bersihkan RM-0010, RM-0016, dan RM-0024 terlebih dahulu agar idempoten saat dijalankan ulang
        for pid in ("RM-0010", "RM-0016", "RM-0024"):
            await client.delete(f"/api/v1/patients/{pid}")

        # 1. Buat RM-0024 (Pasien Kunjungan 1 / Baseline - belum ada kunjungan final)
        r_baseline = await client.post(
            "/api/v1/patients",
            json={
                "id": "RM-0024",
                "nama": "Tn. B",
                "umur": 48,
                "jk": "Laki-laki",
                "lokasi": "Tumit kaki kanan",
                "consent": True,
                "is_demo": True,
            },
        )
        r_baseline.raise_for_status()
        print("[SEED] Pasien RM-0024 (Kunjungan 1 / Baseline) dibuat.")

        # 2. Buat RM-0016 (Pasien 1 Kunjungan Final berisi citra dari ml/test_set)
        r_p16 = await client.post(
            "/api/v1/patients",
            json={
                "id": "RM-0016",
                "nama": "Ny. L",
                "umur": 45,
                "jk": "Perempuan",
                "lokasi": "Telapak kaki kiri",
                "consent": True,
                "is_demo": True,
            },
        )
        r_p16.raise_for_status()
        img_p16 = _find_test_image("Images/Patient_16/P16T_1.jpg")
        r_d16 = await client.post(
            "/api/v1/patients/RM-0016/visits",
            data={"visit_date": "2026-10-10", "distance_confirmed": "true"},
            files={"file": (img_p16.name, img_p16.read_bytes(), "image/jpeg")},
        )
        r_d16.raise_for_status()
        r_c16 = await client.post(f"/api/v1/visits/{r_d16.json()['id']}/confirm")
        r_c16.raise_for_status()
        print(
            f"[SEED] RM-0016 Kunjungan ke-1 (2026-10-10) dikonfirmasi: "
            f"A_t={r_c16.json()['area_pct']}%, image={r_c16.json()['image_path']}"
        )

        # 2. Buat RM-0010 (Pasien 2 Kunjungan Final dengan Citra dari ml/test_set)
        r_pat = await client.post(
            "/api/v1/patients",
            json={
                "id": "RM-0010",
                "nama": "Tn. D",
                "umur": 52,
                "jk": "Laki-laki",
                "lokasi": "Telapak kaki kanan",
                "consent": True,
                "is_demo": True,
            },
        )
        r_pat.raise_for_status()

        visits_spec = [
            ("2026-10-03", "Images/Patient_10/P10T_1.jpg"),
            ("2026-10-17", "Images/Patient_10/P10T_2.jpg"),
        ]
        for v_date, rel_img in visits_spec:
            img_path = _find_test_image(rel_img)
            r_draft = await client.post(
                "/api/v1/patients/RM-0010/visits",
                data={
                    "visit_date": v_date,
                    "distance_confirmed": "true",
                },
                files={
                    "file": (img_path.name, img_path.read_bytes(), "image/jpeg"),
                },
            )
            r_draft.raise_for_status()
            draft_id = r_draft.json()["id"]

            r_conf = await client.post(f"/api/v1/visits/{draft_id}/confirm")
            r_conf.raise_for_status()
            conf_data = r_conf.json()
            print(
                f"[SEED] RM-0010 Kunjungan ke-{conf_data['visit_index']} ({v_date}) "
                f"dikonfirmasi: A_t={conf_data['area_pct']}%, image={conf_data['image_path']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed atau bersihkan data uji H3.")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Hapus pasien demo H3 (RM-0010 dan RM-0024) beserta seluruh berkas citranya.",
    )
    args = parser.parse_args()
    asyncio.run(seed_h3_test_data(clear=args.clear))


if __name__ == "__main__":
    main()

