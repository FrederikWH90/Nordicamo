"""API routes for the Media Archive: outlet directory and outlet profiles."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.outlets_service import OutletsService

router = APIRouter(prefix="/api/outlets", tags=["outlets"])


@router.get("")
async def outlet_directory(db: Session = Depends(get_db)):
    """Every outlet with counts, coverage dates, recent activity and a 12-month series."""
    return OutletsService(db).directory()


@router.get("/{outlet}")
async def outlet_profile(
    outlet: str,
    latest: int = Query(10, ge=1, le=50),
    similar: int = Query(6, ge=0, le=20),
    db: Session = Depends(get_db),
):
    """One outlet: metadata, activity over time, topic profile, latest articles, similar outlets."""
    profile = OutletsService(db).profile(outlet, latest=latest, similar=similar)
    if profile is None:
        raise HTTPException(status_code=404, detail="Outlet not found")
    return profile
