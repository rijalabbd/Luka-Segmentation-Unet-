from datetime import date, datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient, Visit


BASE_DEMO_RM_CODES = ("RM-0012", "RM-0017", "RM-0023")


async def seed_demo_patients(session: AsyncSession, reset: bool = False) -> None:
    if reset:
        await session.execute(delete(Patient).where(Patient.rm_code.in_(BASE_DEMO_RM_CODES)))
        await session.commit()

    existing_rows = await session.execute(
        select(Patient.rm_code).where(Patient.rm_code.in_(BASE_DEMO_RM_CODES))
    )
    existing_codes = set(existing_rows.scalars().all())
    if len(existing_codes) == len(BASE_DEMO_RM_CODES):
        return

    now = datetime.now(timezone.utc)

    p1 = Patient(
        rm_code="RM-0012",
        name_initial="Tn. S",
        age=54,
        gender="Laki-laki",
        ulcer_location="Telapak kaki kanan",
        informed_consent=True,
        is_demo=True,
        visits=[
            Visit(
                visit_index=1,
                visit_date=date(2026, 10, 3),
                status="final",
                n_wound_px=6724,
                area_pct=10.26,
                confirmed_at=now,
            ),
            Visit(
                visit_index=2,
                visit_date=date(2026, 10, 17),
                status="final",
                n_wound_px=5014,
                area_pct=7.65,
                delta_area=-2.61,
                pac=25.44,
                trend_status="Tren Menurun (Area Luka Mengecil)",
                confirmed_at=now,
            ),
            Visit(
                visit_index=3,
                visit_date=date(2026, 10, 24),
                status="final",
                n_wound_px=5308,
                area_pct=8.10,
                delta_area=-2.16,
                pac=21.05,
                trend_status="Tren Menurun (Area Luka Mengecil)",
                confirmed_at=now,
            ),
        ],
    )

    p2 = Patient(
        rm_code="RM-0017",
        name_initial="Ny. M",
        age=42,
        gender="Perempuan",
        ulcer_location="Tungkai bawah kiri",
        informed_consent=True,
        is_demo=True,
        visits=[
            Visit(
                visit_index=1,
                visit_date=date(2026, 10, 3),
                status="final",
                n_wound_px=3932,
                area_pct=6.00,
                confirmed_at=now,
            ),
            Visit(
                visit_index=2,
                visit_date=date(2026, 10, 17),
                status="final",
                n_wound_px=4456,
                area_pct=6.80,
                delta_area=0.80,
                pac=-13.33,
                trend_status="Tren Meningkat (Area Luka Membesar)",
                confirmed_at=now,
            ),
        ],
    )

    p3 = Patient(
        rm_code="RM-0023",
        name_initial="Tn. K",
        age=61,
        gender="Laki-laki",
        ulcer_location="Punggung kaki kiri",
        informed_consent=True,
        is_demo=True,
        visits=[
            Visit(
                visit_index=1,
                visit_date=date(2026, 10, 8),
                status="final",
                n_wound_px=2752,
                area_pct=4.20,
                confirmed_at=now,
            ),
        ],
    )

    to_add = [p for p in (p1, p2, p3) if p.rm_code not in existing_codes]
    if to_add:
        session.add_all(to_add)
        await session.commit()


async def clear_demo_patients(session: AsyncSession) -> int:
    res = await session.execute(delete(Patient).where(Patient.is_demo.is_(True)))
    await session.commit()
    return res.rowcount or 0


if __name__ == "__main__":
    import asyncio
    from app.core.database import AsyncSessionLocal

    async def _main() -> None:
        async with AsyncSessionLocal() as session:
            await seed_demo_patients(session)

    asyncio.run(_main())


