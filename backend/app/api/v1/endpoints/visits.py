import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.database import DBSession
from app.models.visit import Visit
from app.schemas.visit import VisitResponse
from app.services.narrative import (
    NarrativeFn,
    generate_fallback_narrative,
    get_narrative_service,
)
from app.services.pac import evaluate_pac_and_trend
from app.services.storage import delete_visit_files

router = APIRouter(prefix="/visits", tags=["visits"])

_visit_locks: dict[int, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


async def _get_visit_confirm_lock(visit_id: int) -> asyncio.Lock:
    async with _locks_guard:
        if visit_id not in _visit_locks:
            _visit_locks[visit_id] = asyncio.Lock()
        return _visit_locks[visit_id]


async def _get_visit_or_404(db: DBSession, visit_id: int) -> Visit:
    stmt = select(Visit).where(Visit.id == visit_id)
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
    narrative_service: Annotated[NarrativeFn, Depends(get_narrative_service)],
) -> VisitResponse:
    # 1. Kunci konkurensi in-memory per visit_id agar concurrent request tidak memanggil LLM 2 kali
    lock = await _get_visit_confirm_lock(visit_id)
    async with lock:
        # 2. Transaksi DB 1 singkat dengan SELECT ... FOR UPDATE untuk memeriksa status
        stmt = select(Visit).where(Visit.id == visit_id).with_for_update()
        visit = (await db.execute(stmt)).scalar_one_or_none()
        if visit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data kunjungan #{visit_id} tidak ditemukan.",
            )

        # Idempoten: jika sudah final, langsung kembalikan
        if visit.status == "final":
            return VisitResponse.model_validate(visit)

        stmt_finals = (
            select(Visit)
            .where(Visit.patient_id == visit.patient_id, Visit.status == "final")
            .order_by(Visit.visit_index.asc(), Visit.id.asc())
        )
        final_visits = list((await db.execute(stmt_finals)).scalars().all())
        next_index = len(final_visits) + 1
        current_area = visit.area_pct

        # 3. Hitung metrik & panggil LLM di LUAR transaksi database (tidak menahan lock DB selama 10 detik)
        if next_index == 1:
            # Baseline (A0): delta_area, pac, trend_status, dan narasi bernilai Null; Gemini TIDAK dipanggil
            rounded_delta = None
            rounded_pac = None
            trend_label = None
            clinician_notes = None
            patient_narrative = None
            source = None
        else:
            baseline = final_visits[0]
            delta_a, pac, badge, trend_label = evaluate_pac_and_trend(
                baseline.area_pct, current_area
            )
            rounded_delta = round(delta_a, 2)
            rounded_pac = round(pac, 2) if pac is not None else None

            if baseline.area_pct == 0 or pac is None or badge == "tidak_dapat_dihitung":
                # A0 = 0: jangan panggil Gemini; tampilkan pesan & fallback deterministik
                clinician_notes, patient_narrative, source = generate_fallback_narrative(
                    a0=baseline.area_pct,
                    at=current_area,
                    delta_a=rounded_delta,
                    pac=rounded_pac,
                    badge=badge,
                )
            else:
                # Panggil service narasi (Gemini dengan timeout 10 detik, JSON terstruktur, dan fallback Tabel 3.5)
                clinician_notes, patient_narrative, source = await narrative_service(
                    baseline.area_pct,
                    current_area,
                    rounded_delta,
                    rounded_pac,
                    trend_label,
                    badge,
                )

        # 4. Transaksi DB 2 singkat: simpan hasil final
        stmt_save = select(Visit).where(Visit.id == visit_id).with_for_update()
        visit_to_save = (await db.execute(stmt_save)).scalar_one_or_none()
        if visit_to_save is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data kunjungan #{visit_id} tidak ditemukan saat konfirmasi.",
            )

        if visit_to_save.status == "final":
            return VisitResponse.model_validate(visit_to_save)

        visit_to_save.status = "final"
        visit_to_save.visit_index = next_index
        visit_to_save.confirmed_at = datetime.now(timezone.utc)
        visit_to_save.delta_area = rounded_delta
        visit_to_save.pac = rounded_pac
        visit_to_save.trend_status = trend_label
        visit_to_save.clinician_notes = clinician_notes
        visit_to_save.patient_narrative = patient_narrative
        visit_to_save.narrative_source = source

        await db.commit()
        await db.refresh(visit_to_save)
        return VisitResponse.model_validate(visit_to_save)


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
