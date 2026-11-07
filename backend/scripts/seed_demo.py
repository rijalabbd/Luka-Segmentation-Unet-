import argparse
import asyncio

from app.core.database import AsyncSessionLocal, engine
from app.services.seed import clear_demo_patients, seed_demo_patients


async def main(clear: bool) -> None:
    async with AsyncSessionLocal() as session:
        if clear:
            removed = await clear_demo_patients(session)
            print(f"Cleared {removed} demo patients (is_demo=True).")
        else:
            await seed_demo_patients(session)
            print("Seeded demo patients (RM-0012, RM-0017, RM-0023) with is_demo=True.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage demo patient seed data (is_demo=True)")
    parser.add_argument("--clear", action="store_true", help="Remove only demo patients")
    args = parser.parse_args()
    asyncio.run(main(args.clear))
