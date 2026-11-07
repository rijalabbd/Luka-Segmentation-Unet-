import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.database import DBSession
from app.models.patient import Patient
from app.models.visit import Visit
from app.schemas.visit import ConfirmVisitRequest, VisitResponse
from app.services.narrative import NarrativeServiceFn, get_narrative_service
from app.services.pac import evaluate_pac_and_trend
from app.services.storage import delete_visit_files

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


@router.get("/{visit_id}", response_model=VisitResponse)
async def get_visit(visit_id: int, db: DBSession) -> VisitResponse:
    visit = await _get_visit_or_404(db, visit_id)
    return VisitResponse.model_validate(visit)


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
        baseline_area = final_visits[0].area_pct if final_visits else 0.0

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
        rounded_delta: float | None = None
        rounded_pac: float | None = None
        trend_label: str | None = None
        clinician_notes: str | None = None
        patient_narrative: str | None = None
        narrative_source: str | None = None

        if not is_baseline:
            delta_a, pac, badge, trend_label = evaluate_pac_and_trend(
                baseline_area, visit_area
            )
            rounded_delta = round(delta_a, 2)
            rounded_pac = round(pac, 2) if pac is not None else None

            clinician_notes, patient_narrative, narrative_source = await narrative_service(
                baseline_area,
                visit_area,
                rounded_delta,
                rounded_pac,
                badge,
                trend_label,
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

        if next_index == 1:
            visit_locked.delta_area = None
            visit_locked.pac = None
            visit_locked.trend_status = None
            visit_locked.clinician_notes = None
            visit_locked.patient_narrative = None
            visit_locked.narrative_source = None
        else:
            visit_locked.delta_area = rounded_delta
            visit_locked.pac = rounded_pac
            visit_locked.trend_status = trend_label
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
