from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dashboard_schema import (
    DashboardOverviewResponse,
    DashboardProductDetailResponse,
    DashboardProductListResponse,
)
from app.services.dashboard_service import DashboardDomainError, DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


def _handle(error: DashboardDomainError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))


@router.get("/overview", response_model=DashboardOverviewResponse)
def dashboard_overview(db: Session = Depends(get_db)):
    return DashboardService(db).overview()


@router.get("/products", response_model=DashboardProductListResponse)
def dashboard_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return DashboardService(db).list_products(page=page, page_size=page_size, search=search)


@router.get("/products/{product_id}", response_model=DashboardProductDetailResponse)
def dashboard_product_detail(product_id: int, db: Session = Depends(get_db)):
    try:
        return DashboardService(db).detail(product_id)
    except DashboardDomainError as error:
        raise _handle(error)


__all__ = ["router"]

