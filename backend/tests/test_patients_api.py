from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.patient import Patient, Visit
from app.services.pac import calculate_relative_area, evaluate_pac_and_trend
from app.services.seed import seed_demo_patients


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    test_engine = create_async_engine(settings.resolved_test_database_url, future=True)
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async with TestSessionLocal() as session:
        await session.execute(delete(Visit))
        await session.execute(delete(Patient))
        await session.commit()
        await seed_demo_patients(session)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    async with TestSessionLocal() as session:
        await session.execute(delete(Visit))
        await session.execute(delete(Patient))
        await session.commit()

    app.dependency_overrides.clear()
    await test_engine.dispose()


async def test_01_health_check_connected_to_postgres(client: AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["mode"] == "local_isolated"
    assert body["label"] == "Server Lokal Terhubung · Data Terisolasi"
    assert body["short_label"] == "Lokal · Aman"


async def test_02_list_seeded_demo_patients_and_trend_badges(client: AsyncClient) -> None:
    res = await client.get("/api/v1/patients")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 3

    # RM-0012: A0=10.26, A3=8.10 -> PAC=+21.05%, delta_A=-2.16 -> Tren Menurun (Area Luka Mengecil)
    assert data[0]["id"] == "RM-0012"
    assert data[0]["n"] == 3
    assert data[0]["terakhir"] == "24 Okt 2026"
    assert data[0]["status"] == "menurun"
    assert data[0]["trend_status"] == "Tren Menurun (Area Luka Mengecil)"
    assert data[0]["is_demo"] is True

    # RM-0017: A0=6.00, A2=6.80 -> PAC=-13.33%, delta_A=+0.80 -> Tren Meningkat (Area Luka Membesar)
    assert data[1]["id"] == "RM-0017"
    assert data[1]["n"] == 2
    assert data[1]["terakhir"] == "17 Okt 2026"
    assert data[1]["status"] == "meningkat"
    assert data[1]["trend_status"] == "Tren Meningkat (Area Luka Membesar)"
    assert data[1]["is_demo"] is True

    # RM-0023: 1 kunjungan -> Kunjungan awal (baseline) tanpa kata "Pantau"
    assert data[2]["id"] == "RM-0023"
    assert data[2]["n"] == 1
    assert data[2]["terakhir"] == "08 Okt 2026"
    assert data[2]["status"] == "baseline"
    assert data[2]["trend_status"] == "Kunjungan awal (baseline)"
    assert "Pantau" not in data[2]["trend_status"]
    assert data[2]["is_demo"] is True


async def test_03_filter_patients_by_is_demo_flag(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/patients",
        json={"id": "Patient_10", "nama": "LUTSeg 10", "consent": True, "is_demo": False},
    )
    demo_res = await client.get("/api/v1/patients", params={"is_demo": "true"})
    non_demo_res = await client.get("/api/v1/patients", params={"is_demo": "false"})
    assert len(demo_res.json()) == 3
    assert len(non_demo_res.json()) == 1
    assert non_demo_res.json()[0]["id"] == "PATIENT_10"
    assert non_demo_res.json()[0]["is_demo"] is False


async def test_04_search_patients_with_dot_and_space_normalization(client: AsyncClient) -> None:
    res_q = await client.get("/api/v1/patients", params={"q": "tn s"})
    assert res_q.status_code == 200
    assert len(res_q.json()) == 1
    assert res_q.json()[0]["id"] == "RM-0012"


async def test_05_create_valid_patient(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/patients",
        json={
            "id": "rm-0031",
            "nama": "Tn. B",
            "umur": 48,
            "jk": "Laki-laki",
            "lokasi": "Telapak kaki kiri",
            "consent": True,
        },
    )
    assert res.status_code == 201
    created = res.json()
    assert created["id"] == "RM-0031"
    assert created["n"] == 0
    assert created["status"] == "belum_ada"
    assert created["trend_status"] == "Belum ada kunjungan"
    assert created["terakhir"] == "Belum ada kunjungan"
    assert created["is_demo"] is False


async def test_06_reject_duplicate_rm_case_insensitive_409(client: AsyncClient) -> None:
    dup = await client.post(
        "/api/v1/patients",
        json={"id": "rm-0012", "consent": True},
    )
    assert dup.status_code == 409
    assert "sudah terdaftar" in dup.json()["detail"]


async def test_07_reject_missing_informed_consent_422(client: AsyncClient) -> None:
    no_consent = await client.post(
        "/api/v1/patients",
        json={"id": "RM-0099", "consent": False},
    )
    assert no_consent.status_code == 422


async def test_08_reject_invalid_rm_format_422(client: AsyncClient) -> None:
    bad_rm = await client.post(
        "/api/v1/patients",
        json={"id": "A!", "consent": True},
    )
    assert bad_rm.status_code == 422


async def test_09_reject_out_of_bounds_age_422(client: AsyncClient) -> None:
    bad_age = await client.post(
        "/api/v1/patients",
        json={"id": "RM-0088", "umur": 150, "consent": True},
    )
    assert bad_age.status_code == 422


async def test_10_pac_and_trend_evaluation_menurun_meningkat_stabil() -> None:
    # Contoh Bab 3.7: N_luka T1=3277 (5.00%), T2=2294 (3.50%) -> delta_A=-1.50, PAC=+30.0%
    a0 = round(calculate_relative_area(3277), 2)
    at = round(calculate_relative_area(2294), 2)
    assert a0 == 5.00
    assert at == 3.50
    delta_a, pac, badge, label = evaluate_pac_and_trend(a0, at)
    assert round(delta_a, 2) == -1.50
    assert round(pac or 0.0, 1) == 30.0
    assert badge == "menurun"
    assert label == "Tren Menurun (Area Luka Mengecil)"

    # Stabil: PAC dalam [-5, +5] dan delta_A dalam [-1, +1]
    _, pac_s, badge_s, label_s = evaluate_pac_and_trend(10.0, 9.7)
    assert round(pac_s or 0.0, 1) == 3.0
    assert badge_s == "stabil"
    assert label_s == "Tren Stabil (Perubahan Minimal)"

    # Meningkat: PAC < -5.0 atau delta_A > +1.0
    _, pac_m, badge_m, label_m = evaluate_pac_and_trend(5.0, 6.0)
    assert round(pac_m or 0.0, 1) == -20.0
    assert badge_m == "meningkat"
    assert label_m == "Tren Meningkat (Area Luka Membesar)"


async def test_11_pac_zero_baseline_division_guard() -> None:
    delta_a, pac, badge, label = evaluate_pac_and_trend(0.0, 2.5)
    assert delta_a == 2.5
    assert pac is None
    assert badge == "tidak_dapat_dihitung"
    assert label == "PAC tidak dapat dihitung"


async def test_12_get_patient_by_rm_code_and_404(client: AsyncClient) -> None:
    ok_res = await client.get("/api/v1/patients/rm-0012")
    assert ok_res.status_code == 200
    assert ok_res.json()["id"] == "RM-0012"

    not_found = await client.get("/api/v1/patients/RM-9999")
    assert not_found.status_code == 404
