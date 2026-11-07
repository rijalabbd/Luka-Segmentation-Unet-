from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.api.v1.endpoints.patients import router as patients_router
from app.api.v1.endpoints.visits import router as visits_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, DBSession
from app.services.seed import seed_demo_patients
from app.services.segmentation import load_segmentation_model
from app.services.storage import (
    ALLOWED_STORAGE_SUBDIRS,
    get_storage_root,
    resolve_storage_path,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    get_storage_root()
    load_segmentation_model()
    if settings.seed_demo_on_startup:
        async with AsyncSessionLocal() as session:
            await seed_demo_patients(session)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.api_v1_prefix}/health", tags=["system"])
async def health_check(db: DBSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "mode": "local_isolated",
        "label": "Server Lokal Terhubung · Data Terisolasi",
        "short_label": "Lokal · Aman",
    }


@app.get(f"{settings.api_v1_prefix}/storage/{{subdir}}/{{filename}}", tags=["storage"])
async def get_stored_file(subdir: str, filename: str) -> FileResponse:
    if (
        subdir not in ALLOWED_STORAGE_SUBDIRS
        or not filename
        or "/" in filename
        or "\\" in filename
        or ".." in filename
        or ".." in subdir
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas tidak ditemukan.",
        )
    try:
        file_path: Path = resolve_storage_path(f"{subdir}/{filename}")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas tidak ditemukan.",
        ) from exc

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas tidak ditemukan.",
        )
    return FileResponse(file_path)


app.include_router(patients_router, prefix=settings.api_v1_prefix)
app.include_router(visits_router, prefix=settings.api_v1_prefix)
