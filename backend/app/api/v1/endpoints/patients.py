from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import DBSession
from app.models.patient import Patient, Visit
from app.schemas.patient import PatientCreate, PatientSummaryResponse
from app.schemas.visit import VisitResponse
from app.services.pac import build_patient_summary, calculate_relative_area
from app.services.segmentation import SegmentationDep
from app.services.storage import (
    delete_visit_files,
    save_visit_files,
    validate_and_orient_image_bytes,
)

router = APIRouter(prefix="/patients", tags=["patients"])

# Daftar putih ketat berkas foto sampel dari ml/test_set (S6)
DEMO_SAMPLE_PHOTO_WHITELIST: dict[str, str] = {
    "P10T_1.jpg": "Images/Patient_10/P10T_1.jpg",
    "P10T_2.jpg": "Images/Patient_10/P10T_2.jpg",
    "P10T_3.jpg": "Images/Patient_10/P10T_3.jpg",
    "P16T_1.jpg": "Images/Patient_16/P16T_1.jpg",
    "P16T_2.jpg": "Images/Patient_16/P16T_2.jpg",
    "P17T_1.jpg": "Images/Patient_17/P17T_1.jpg",
    "P17T_2.jpg": "Images/Patient_17/P17T_2.jpg",
    "P22T_1.jpg": "Images/Patient_22/P22T_1.jpg",
    "P23T_1.jpg": "Images/Patient_23/P23T_1.jpg",
    "P23T_2.jpg": "Images/Patient_23/P23T_2.jpg",
    "P25T_1.jpg": "Images/Patient_25/P25T_1.jpg",
}

DEFAULT_DEMO_SAMPLE_BY_RM: dict[str, str] = {
    "RM-0010": "P10T_3.jpg",
    "RM-0012": "P25T_1.jpg",
    "RM-0016": "P16T_2.jpg",
    "RM-0017": "P17T_2.jpg",
    "RM-0023": "P23T_2.jpg",
    "RM-0024": "P22T_1.jpg",
}


def _resolve_test_set_sample(rel_path: str) -> Path:
    for root_candidate in (
        Path("/app/ml/test_set"),
        Path("ml/test_set"),
        Path("../ml/test_set"),
    ):
        if root_candidate.is_dir():
            root_resolved = root_candidate.resolve()
            target = (root_resolved / rel_path).resolve()
            if root_resolved in target.parents and target.is_file():
                return target
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Berkas foto sampel tidak ditemukan di ml/test_set.",
    )


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return " ".join(s.lower().replace(".", "").split())


async def _get_patient_or_404(db: DBSession, patient_id: str) -> Patient:
    normalized = patient_id.strip().upper()
    stmt = (
        select(Patient)
        .options(selectinload(Patient.visits))
        .where(func.upper(Patient.rm_code) == normalized)
    )
    result = await db.execute(stmt)
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data pasien {normalized} tidak ditemukan.",
        )
    return patient


@router.get("", response_model=list[PatientSummaryResponse])
async def list_patients(
    db: DBSession,
    q: Annotated[
        str | None, Query(description="Cari kode RM, inisial nama, atau lokasi ulkus")
    ] = None,
    is_demo: Annotated[
        bool | None, Query(description="Filter pasien demo (true/false)")
    ] = None,
) -> list[PatientSummaryResponse]:
    stmt = select(Patient).options(selectinload(Patient.visits)).order_by(Patient.rm_code.asc())
    if is_demo is not None:
        stmt = stmt.where(Patient.is_demo.is_(is_demo))

    result = await db.execute(stmt)
    patients = result.scalars().all()
    summaries = [build_patient_summary(p) for p in patients]

    if q and q.strip():
        term = _norm(q)
        summaries = [
            s
            for s in summaries
            if any(term in _norm(field) for field in (s.id, s.nama, s.lokasi))
        ]
    return summaries


@router.get("/{patient_id}", response_model=PatientSummaryResponse)
async def get_patient(patient_id: str, db: DBSession) -> PatientSummaryResponse:
    patient = await _get_patient_or_404(db, patient_id)
    return build_patient_summary(patient)


@router.post("", response_model=PatientSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate, db: DBSession) -> PatientSummaryResponse:
    stmt = select(Patient).where(func.upper(Patient.rm_code) == payload.id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nomor RM ini sudah terdaftar. Pilih dari tab Pasien Lama.",
        )

    patient = Patient(
        rm_code=payload.id,
        name_initial=payload.nama,
        age=payload.umur,
        gender=payload.jk,
        ulcer_location=payload.lokasi,
        informed_consent=payload.consent,
        is_demo=payload.is_demo,
    )
    db.add(patient)
    await db.commit()

    refreshed = await _get_patient_or_404(db, patient.rm_code)
    return build_patient_summary(refreshed)


@router.post(
    "/{patient_id}/visits",
    response_model=VisitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft_visit(
    patient_id: str,
    db: DBSession,
    visit_date: Annotated[date, Form(description="Tanggal kunjungan dari form H3")],
    file: Annotated[UploadFile, File(description="Berkas foto luka")],
    segment_fn: SegmentationDep,
    distance_confirmed: Annotated[
        bool, Form(description="Konfirmasi keseragaman jarak dan sudut pemotretan")
    ] = False,
) -> VisitResponse:
    if not distance_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Konfirmasi keseragaman jarak dan sudut pemotretan wajib dicentang.",
        )

    patient = await _get_patient_or_404(db, patient_id)

    # Toleransi batas atas 1 hari dari jam UTC agar pukul 00.00-07.00 WIB tidak ditolak
    max_allowed_date = datetime.now(timezone.utc).date() + timedelta(days=1)
    if visit_date > max_allowed_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Tanggal pemeriksaan ({visit_date.isoformat()}) melewati batas tanggal hari ini."
            ),
        )

    final_dates = [v.visit_date for v in patient.visits if v.status == "final"]
    if final_dates:
        latest_final_date = max(final_dates)
        if visit_date < latest_final_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Tanggal pemeriksaan ({visit_date.isoformat()}) tidak boleh lebih awal "
                    f"dari kunjungan final terakhir ({latest_final_date.isoformat()})."
                ),
            )

    # Batasi pembacaan memori sebesar max_upload_size_bytes + 1 byte untuk mencegah alokasi berlebih
    image_bytes = await file.read(settings.max_upload_size_bytes + 1)
    try:
        _rgb_img, clean_bytes, ext = await run_in_threadpool(
            validate_and_orient_image_bytes, image_bytes
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    n_wound_px, mask_bytes = await run_in_threadpool(segment_fn, image_bytes)
    safe_filename = f"upload{ext}" if not file.filename else file.filename
    image_rel, mask_rel = await run_in_threadpool(
        save_visit_files,
        patient.rm_code,
        clean_bytes,
        safe_filename,
        mask_bytes,
        None,
    )
    area_pct = round(calculate_relative_area(n_wound_px), 2)

    # Hanya satu draft aktif per pasien; hapus draft lama setelah berkas baru berhasil dibuat
    old_drafts = [v for v in patient.visits if v.status == "draft"]
    for old_draft in old_drafts:
        delete_visit_files(old_draft.image_path, old_draft.mask_path)
        await db.delete(old_draft)
    if old_drafts:
        await db.flush()

    draft = Visit(
        patient_id=patient.rm_code,
        visit_date=visit_date,
        status="draft",
        visit_index=None,
        image_path=image_rel,
        mask_path=mask_rel,
        distance_confirmed=True,
        n_wound_px=n_wound_px,
        area_pct=area_pct,
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return VisitResponse.model_validate(draft)


@router.get("/{patient_id}/visits", response_model=list[VisitResponse])
async def list_patient_final_visits(
    patient_id: str,
    db: DBSession,
    status: Annotated[
        Literal["final", "draft", "all"],
        Query(description="Filter status kunjungan: final (default), draft, atau all"),
    ] = "final",
) -> list[VisitResponse]:
    patient = await _get_patient_or_404(db, patient_id)
    filtered = [v for v in patient.visits if status == "all" or v.status == status]
    ordered = sorted(
        filtered,
        key=lambda v: (v.visit_index if v.visit_index is not None else 999999, v.visit_date, v.id),
    )
    return [VisitResponse.model_validate(v) for v in ordered]


@router.get("/{patient_id}/sample-photo")
async def get_demo_sample_photo(
    patient_id: str,
    db: DBSession,
    filename: Annotated[
        str | None,
        Query(description="Nama berkas dari daftar putih ml/test_set (opsional)"),
    ] = None,
) -> Response:
    patient = await _get_patient_or_404(db, patient_id)
    if not patient.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foto sampel hanya tersedia untuk pasien mode demo (is_demo=true).",
        )

    chosen_name = filename or DEFAULT_DEMO_SAMPLE_BY_RM.get(
        patient.rm_code.upper(), "P10T_3.jpg"
    )
    rel_path = DEMO_SAMPLE_PHOTO_WHITELIST.get(chosen_name)
    if rel_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nama berkas foto sampel tidak ada dalam daftar putih.",
        )

    img_path = _resolve_test_set_sample(rel_path)
    return Response(
        content=img_path.read_bytes(),
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'inline; filename="{chosen_name}"',
            "X-Sample-Filename": chosen_name,
        },
    )


@router.delete("/{patient_id}")
async def delete_patient(patient_id: str, db: DBSession) -> dict[str, str | int]:
    patient = await _get_patient_or_404(db, patient_id)
    visit_count = len(patient.visits)
    for v in patient.visits:
        delete_visit_files(v.image_path, v.mask_path)

    rm_code = patient.rm_code
    await db.delete(patient)
    await db.commit()
    return {
        "deleted_patient_id": rm_code,
        "deleted_visits": visit_count,
    }
