import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from PIL import Image, ImageOps
from sqlalchemy import func, select

from app.core.database import DBSession
from app.models.patient import Patient
from app.models.visit import Visit
from app.schemas.visit import (
    CalibrationRequest,
    ConfirmVisitRequest,
    VisitPreview,
    VisitResponse,
)
from app.services.calibration import (
    CalibrationValidationError,
    compute_and_validate_calibration,
)
from app.services.narrative import NarrativeServiceFn, get_narrative_service
from app.services.pac import LongitudinalEvaluation, evaluate_visit_longitudinal
from app.services.storage import delete_visit_files, resolve_storage_path

router = APIRouter(prefix="/visits", tags=["visits"])

NarrativeDep = Annotated[NarrativeServiceFn, Depends(get_narrative_service)]

# shortcut: kunci asyncio.Lock per visit_id di memori hanya berlaku untuk satu worker uvicorn (backend/Dockerfile menjalankan fastapi run tanpa --workers); gunakan pg_advisory_lock jika kelak berjalan multi-worker.
_confirm_locks: dict[int, asyncio.Lock] = {}


def _get_visit_confirm_lock(visit_id: int) -> asyncio.Lock:
    lock = _confirm_locks.get(visit_id)
    if lock is None:
        if len(_confirm_locks) > 2048:
            unlocked = [k for k, v in _confirm_locks.items() if not v.locked()]
            for k in unlocked[:1024]:
                _confirm_locks.pop(k, None)
        lock = asyncio.Lock()
        _confirm_locks[visit_id] = lock
    return lock


async def _get_visit_or_404(
    db: DBSession, visit_id: int, *, for_update: bool = False
) -> Visit:
    stmt = select(Visit).where(Visit.id == visit_id)
    if for_update:
        stmt = stmt.with_for_update()
    visit = (await db.execute(stmt)).scalar_one_or_none()
    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data kunjungan #{visit_id} tidak ditemukan.",
        )
    return visit


def _resolve_visit_image_dimensions(visit: Visit) -> tuple[int, int]:
    if (
        visit.img_width_px is not None
        and visit.img_height_px is not None
        and visit.img_width_px > 0
        and visit.img_height_px > 0
    ):
        return visit.img_width_px, visit.img_height_px
    if visit.image_path:
        try:
            abs_path = resolve_storage_path(visit.image_path)
            if abs_path.is_file():
                with Image.open(abs_path) as img:
                    oriented = ImageOps.exif_transpose(img)
                    return int(oriented.width), int(oriented.height)
        except Exception:
            pass
    return 256, 256


async def _build_visit_response(db: DBSession, visit: Visit) -> VisitResponse:
    resp = VisitResponse.model_validate(visit)
    if visit.status != "draft":
        return resp

    stmt = (
        select(Visit)
        .where(Visit.patient_id == visit.patient_id, Visit.status == "final")
        .order_by(Visit.visit_index.asc(), Visit.id.asc())
    )
    final_visits = list((await db.execute(stmt)).scalars().all())
    if not final_visits:
        resp.preview = VisitPreview(is_baseline=True)
        return resp

    baseline = final_visits[0]
    eval_res = evaluate_visit_longitudinal(baseline, visit)
    resp.preview = VisitPreview(
        is_baseline=False,
        pac_basis=eval_res.pac_basis,
        delta_area=eval_res.delta_area,
        pac=eval_res.pac,
        pac_rel=eval_res.pac_rel,
        pac_cm2=eval_res.pac_cm2,
        trend_status=eval_res.trend_status,
        warnings=list(eval_res.warnings),
    )
    return resp


@router.get("/{visit_id}", response_model=VisitResponse)
async def get_visit(visit_id: int, db: DBSession) -> VisitResponse:
    visit = await _get_visit_or_404(db, visit_id)
    return await _build_visit_response(db, visit)


@router.put("/{visit_id}/calibration", response_model=VisitResponse)
async def put_visit_calibration(
    visit_id: int,
    payload: CalibrationRequest,
    db: DBSession,
) -> VisitResponse:
    visit = await _get_visit_or_404(db, visit_id, for_update=True)
    if visit.status != "draft":
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kunjungan yang sudah final tidak dapat dikalibrasi ulang.",
        )

    width_px, height_px = _resolve_visit_image_dimensions(visit)
    try:
        cal = compute_and_validate_calibration(
            x1=payload.x1,
            y1=payload.y1,
            x2=payload.x2,
            y2=payload.y2,
            length_cm=payload.length_cm,
            width_px=width_px,
            height_px=height_px,
            n_wound_px=visit.n_wound_px,
        )
    except CalibrationValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    visit.measure_mode = "calibrated"
    visit.img_width_px = width_px
    visit.img_height_px = height_px
    visit.calib_x1 = payload.x1
    visit.calib_y1 = payload.y1
    visit.calib_x2 = payload.x2
    visit.calib_y2 = payload.y2
    visit.calib_length_cm = payload.length_cm
    visit.scale_cm_per_px = cal.scale_cm_per_px
    visit.area_cm2 = cal.area_cm2

    await db.commit()
    await db.refresh(visit)
    return await _build_visit_response(db, visit)


@router.delete("/{visit_id}/calibration", response_model=VisitResponse)
async def delete_visit_calibration(
    visit_id: int,
    db: DBSession,
) -> VisitResponse:
    visit = await _get_visit_or_404(db, visit_id, for_update=True)
    if visit.status != "draft":
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kalibrasi pada kunjungan final tidak dapat dihapus.",
        )

    visit.measure_mode = "relative"
    visit.calib_x1 = None
    visit.calib_y1 = None
    visit.calib_x2 = None
    visit.calib_y2 = None
    visit.calib_length_cm = None
    visit.scale_cm_per_px = None
    visit.area_cm2 = None

    await db.commit()
    await db.refresh(visit)
    return await _build_visit_response(db, visit)


@router.post("/{visit_id}/confirm", response_model=VisitResponse)
async def confirm_visit(
    visit_id: int,
    db: DBSession,
    narrative_service: NarrativeDep,
    payload: Annotated[ConfirmVisitRequest | None, Body()] = None,
    confirm_zero_area: Annotated[bool, Query()] = False,
) -> VisitResponse:
    confirmed_zero = bool(
        confirm_zero_area or (payload is not None and payload.confirm_zero_area)
    )
    lock = _get_visit_confirm_lock(visit_id)
    async with lock:
        # Transaksi 1 (singkat): kunci baris visit, periksa status & validitas A_t, lalu lepaskan transaksi
        visit = await _get_visit_or_404(db, visit_id, for_update=True)

        # Aturan bisnis: confirm bersifat idempoten
        if visit.status == "final":
            resp = VisitResponse.model_validate(visit)
            await db.rollback()
            return resp

        patient_id = visit.patient_id
        visit_area = visit.area_pct
        is_zero_area = visit.n_wound_px <= 0 or visit.area_pct <= 0.0

        stmt = (
            select(Visit)
            .where(Visit.patient_id == patient_id, Visit.status == "final")
            .order_by(Visit.visit_index.asc(), Visit.id.asc())
        )
        final_visits = list((await db.execute(stmt)).scalars().all())
        is_baseline = len(final_visits) == 0
        eval_res: LongitudinalEvaluation | None = (
            evaluate_visit_longitudinal(final_visits[0], visit) if not is_baseline else None
        )

        # Aturan S1:
        # - Baseline dengan n_wound_px = 0 (A_t = 0): selalu ditolak (422).
        # - Kunjungan lanjutan dengan n_wound_px = 0 (A_t = 0): izinkan hanya jika confirm_zero_area=true.
        if is_zero_area:
            if is_baseline:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "Konfirmasi baseline ditolak: tidak ada area luka yang terdeteksi pada citra "
                        "kunjungan awal (A_t = 0%). Silakan buang draf dan ambil foto ulang."
                    ),
                )
            if not confirmed_zero:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "Konfirmasi ditolak: tidak ada area luka yang terdeteksi pada citra "
                        "(A_t = 0%). Kirim confirm_zero_area=true jika Anda sudah memeriksa bahwa "
                        "luka memang tidak terlihat pada foto ini, atau lakukan Foto Ulang."
                    ),
                )

        # Akhiri transaksi baca agar koneksi DB tidak ditahan selama pemanggilan Gemini (hingga 10 detik)
        await db.rollback()

        # Di luar transaksi database: hitung PAC & panggil layanan narasi (Gemini + validator + fallback)
        clinician_notes: str | None = None
        patient_narrative: str | None = None
        narrative_source: str | None = None

        if eval_res is not None:
            if eval_res.pac_basis == "calibrated":
                clinician_notes, patient_narrative, narrative_source = await narrative_service(
                    eval_res.a0,
                    eval_res.at,
                    eval_res.delta_area,
                    eval_res.pac,
                    eval_res.badge,
                    eval_res.trend_status,
                    unit="cm²",
                )
            else:
                clinician_notes, patient_narrative, narrative_source = await narrative_service(
                    eval_res.a0,
                    eval_res.at,
                    eval_res.delta_area,
                    eval_res.pac,
                    eval_res.badge,
                    eval_res.trend_status,
                )

        # Transaksi 2 (singkat): kunci baris pasien dan visit, tetapkan visit_index, dan simpan final
        await db.execute(
            select(Patient).where(Patient.rm_code == patient_id).with_for_update()
        )
        visit_locked = await _get_visit_or_404(db, visit_id, for_update=True)
        if visit_locked.status == "final":
            resp_locked = VisitResponse.model_validate(visit_locked)
            await db.rollback()
            return resp_locked

        final_visits_locked = list((await db.execute(stmt)).scalars().all())
        next_index = len(final_visits_locked) + 1
        locked_is_zero = visit_locked.n_wound_px <= 0 or visit_locked.area_pct <= 0.0

        if locked_is_zero:
            if next_index == 1:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "Konfirmasi baseline ditolak: tidak ada area luka yang terdeteksi pada citra "
                        "kunjungan awal (A_t = 0%). Silakan buang draf dan ambil foto ulang."
                    ),
                )
            if not confirmed_zero:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "Konfirmasi ditolak: tidak ada area luka yang terdeteksi pada citra "
                        "(A_t = 0%). Kirim confirm_zero_area=true jika Anda sudah memeriksa bahwa "
                        "luka memang tidak terlihat pada foto ini, atau lakukan Foto Ulang."
                    ),
                )

        visit_locked.status = "final"
        visit_locked.visit_index = next_index
        visit_locked.confirm_zero_area = bool(locked_is_zero and confirmed_zero)
        visit_locked.confirmed_at = datetime.now(timezone.utc)

        if next_index == 1 or eval_res is None:
            visit_locked.delta_area = None
            visit_locked.pac = None
            visit_locked.pac_rel = None
            visit_locked.pac_cm2 = None
            visit_locked.pac_basis = None
            visit_locked.warnings = []
            visit_locked.trend_status = None
            visit_locked.clinician_notes = None
            visit_locked.patient_narrative = None
            visit_locked.narrative_source = None
        else:
            visit_locked.delta_area = eval_res.delta_area
            visit_locked.pac = eval_res.pac
            visit_locked.pac_rel = eval_res.pac_rel
            visit_locked.pac_cm2 = eval_res.pac_cm2
            visit_locked.pac_basis = eval_res.pac_basis
            visit_locked.warnings = list(eval_res.warnings)
            visit_locked.trend_status = eval_res.trend_status
            visit_locked.clinician_notes = clinician_notes
            visit_locked.patient_narrative = patient_narrative
            visit_locked.narrative_source = narrative_source

        await db.commit()
        await db.refresh(visit_locked)
        return VisitResponse.model_validate(visit_locked)


@router.delete("/{visit_id}")
async def delete_visit(visit_id: int, db: DBSession) -> dict[str, int | str]:
    visit = await _get_visit_or_404(db, visit_id)

    if visit.status == "final":
        max_idx_stmt = select(func.max(Visit.visit_index)).where(
            Visit.patient_id == visit.patient_id,
            Visit.status == "final",
        )
        max_idx = (await db.execute(max_idx_stmt)).scalar_one_or_none()
        if max_idx is not None and visit.visit_index != max_idx:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Penghapusan ditolak (aturan LIFO): hanya kunjungan final terakhir yang dapat dihapus.",
            )

    deleted_status = visit.status
    delete_visit_files(visit.image_path, visit.mask_path)
    await db.delete(visit)
    await db.commit()
    return {
        "deleted_visit_id": visit_id,
        "status": deleted_status,
    }
