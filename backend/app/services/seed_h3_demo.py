"""
Skrip reset dan seeding data demo lengkap (Langkah 0d & Bagian 10 PRD):
- Memastikan seluruh pasien demo dasar (RM-0012, RM-0017, RM-0023) dan pasien demo H3
  (RM-0010 dengan 2 kunjungan bercitra, RM-0016 dengan 1 kunjungan bercitra, RM-0024 dengan 0 kunjungan)
  tersedia secara konsisten.
- Membersihkan seluruh berkas yatim di storage (uploads, masks, overlays) yang tidak memiliki
  baris di tabel visits.
- Dapat dibersihkan kembali dengan argumen `--clear`.
"""
import argparse
import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.visit import Visit, derive_overlay_rel_path
from app.services.segmentation import get_loaded_model, load_segmentation_model
from app.services.seed import BASE_DEMO_RM_CODES, seed_demo_patients
from app.services.storage import ALLOWED_STORAGE_SUBDIRS, get_storage_root

H3_DEMO_RM_CODES = ("RM-0010", "RM-0016", "RM-0024")
ALL_DEMO_RM_CODES = BASE_DEMO_RM_CODES + H3_DEMO_RM_CODES


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


async def cleanup_orphan_storage_files(session: AsyncSession) -> list[str]:
    rows = (await session.execute(select(Visit.image_path, Visit.mask_path))).all()
    referenced: set[str] = set()
    for img_rel, mask_rel in rows:
        if img_rel:
            referenced.add(img_rel.replace("\\", "/"))
        if mask_rel:
            referenced.add(mask_rel.replace("\\", "/"))
            overlay_rel = derive_overlay_rel_path(mask_rel)
            if overlay_rel:
                referenced.add(overlay_rel.replace("\\", "/"))

    root = get_storage_root()
    removed: list[str] = []
    for subdir in ALLOWED_STORAGE_SUBDIRS:
        folder = root / subdir
        if not folder.is_dir():
            continue
        for item in sorted(folder.iterdir()):
            if not item.is_file() or item.name == ".gitkeep":
                continue
            rel = f"{subdir}/{item.name}"
            if rel not in referenced:
                item.unlink()
                removed.append(rel)
    return removed


async def seed_h3_test_data(clear: bool = False) -> None:
    if get_loaded_model() is None:
        load_segmentation_model()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        if clear:
            for pid in ALL_DEMO_RM_CODES:
                res = await client.delete(f"/api/v1/patients/{pid}")
                if res.status_code == 200:
                    print(f"[CLEAR] Pasien {pid} beserta berkas citranya dihapus.")
                else:
                    print(f"[CLEAR] Pasien {pid} tidak ada (HTTP {res.status_code}).")
            async with AsyncSessionLocal() as session:
                orphans = await cleanup_orphan_storage_files(session)
            print(f"[ORPHAN-CLEANUP] {len(orphans)} berkas yatim dihapus dari storage.")
            return

        # Bersihkan H3 demo terlebih dahulu agar idempoten saat dijalankan ulang
        for pid in H3_DEMO_RM_CODES:
            await client.delete(f"/api/v1/patients/{pid}")

        # 0. Reset dan buat pasien demo dasar (RM-0012, RM-0017, RM-0023)
        async with AsyncSessionLocal() as session:
            await seed_demo_patients(session, reset=True)
        print(
            "[SEED] Pasien demo dasar dibuat: "
            "RM-0012 (3 kunjungan), RM-0017 (2 kunjungan), RM-0023 (1 kunjungan)."
        )

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

        # 3. Buat RM-0010 (Pasien 2 Kunjungan Final dengan Citra dari ml/test_set)
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

        async with AsyncSessionLocal() as session:
            orphans = await cleanup_orphan_storage_files(session)
        print(f"[ORPHAN-CLEANUP] {len(orphans)} berkas yatim dihapus dari storage.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset atau bersihkan seluruh data demo.")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Hapus seluruh pasien demo beserta berkas citra dan berkas yatim di storage.",
    )
    args = parser.parse_args()
    asyncio.run(seed_h3_test_data(clear=args.clear))


if __name__ == "__main__":
    main()
