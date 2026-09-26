"""API routes for article search."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.articles_service import ArticlesService
from app.services.selection_service import MAX_SAMPLE, SelectionService

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("/search")
async def search_articles(
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    sentiment: Optional[str] = None,
    categories: Optional[str] = None,
    entities: Optional[str] = None,
    outlets: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    service = ArticlesService(db)

    category_list: Optional[List[str]] = categories.split(",") if categories else None
    entity_list: Optional[List[str]] = entities.split(",") if entities else None
    outlet_list: Optional[List[str]] = outlets.split(",") if outlets else None

    return service.search_articles(
        query=q,
        date_from=date_from,
        date_to=date_to,
        country=country,
        partisan=partisan,
        sentiment=sentiment,
        categories=category_list,
        entities=entity_list,
        outlets=outlet_list,
        limit=limit,
        offset=offset,
    )


@router.get("/selection")
async def describe_selection(
    countries: Optional[List[str]] = Query(None, description="Repeat per country"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    partisan: Optional[str] = None,
    outlets: Optional[List[str]] = Query(None, description="Repeat per outlet domain"),
    topics: Optional[List[str]] = Query(None, description="Repeat per topic; matches any"),
    q: Optional[str] = Query(None, description='Keywords: word, prefix*, "phrase", OR, -exclude'),
    sample_size: int = Query(25, ge=0, le=MAX_SAMPLE),
    order: str = Query("random", pattern="^(random|newest)$"),
    seed: str = Query("nordicamo", max_length=40),
    db: Session = Depends(get_db),
):
    """Count, composition and a metadata-only sample for one article selection."""
    return SelectionService(db).describe(
        countries=countries,
        date_from=date_from,
        date_to=date_to,
        partisan=partisan,
        outlets=outlets,
        topics=topics,
        q=q,
        sample_size=sample_size,
        order=order,
        seed=seed,
    )
