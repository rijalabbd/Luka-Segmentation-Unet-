from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.database import DBSession
from app.models.visit import Visit
from app.schemas.visit import VisitResponse
from app.services.narrative import generate_fallback_narrative
from app.services.pac import evaluate_pac_and_trend
from app.services.storage import delete_visit_files

router = APIRouter(prefix="/visits", tags=["visits"])


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
async def confirm_visit(visit_id: int, db: DBSession) -> VisitResponse:
    visit = await _get_visit_or_404(db, visit_id)

    # Aturan bisnis: confirm bersifat idempoten
    if visit.status == "final":
        return VisitResponse.model_validate(visit)

    stmt = (
        select(Visit)
        .where(Visit.patient_id == visit.patient_id, Visit.status == "final")
        .order_by(Visit.visit_index.asc(), Visit.id.asc())
    )
    final_visits = list((await db.execute(stmt)).scalars().all())
    next_index = len(final_visits) + 1

    visit.status = "final"
    visit.visit_index = next_index
    visit.confirmed_at = datetime.now(timezone.utc)

    if next_index == 1:
        # Baseline (A0): delta_area, pac, trend_status, dan narasi bernilai Null
        visit.delta_area = None
        visit.pac = None
        visit.trend_status = None
        visit.clinician_notes = None
        visit.patient_narrative = None
        visit.narrative_source = None
    else:
        baseline = final_visits[0]
        delta_a, pac, badge, trend_label = evaluate_pac_and_trend(
            baseline.area_pct, visit.area_pct
        )
        rounded_delta = round(delta_a, 2)
        rounded_pac = round(pac, 2) if pac is not None else None

        visit.delta_area = rounded_delta
        visit.pac = rounded_pac
        visit.trend_status = trend_label

        clinician_notes, patient_narrative, source = generate_fallback_narrative(
            a0=baseline.area_pct,
            at=visit.area_pct,
            delta_a=rounded_delta,
            pac=rounded_pac,
            badge=badge,
        )
        visit.clinician_notes = clinician_notes
        visit.patient_narrative = patient_narrative
        visit.narrative_source = source

    await db.commit()
    await db.refresh(visit)
    return VisitResponse.model_validate(visit)


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

