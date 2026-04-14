from __future__ import annotations
"""
Company insights route.
GET /api/company/insights?name=TCS&role=Data+Analyst
"""
from fastapi import APIRouter, Depends, Query
from backend.scrapers.ambitionbox import get_company_insights
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/company", tags=["company"])


@router.get("/insights")
def company_insights(
    name: str = Query(...),
    role: str = Query(default=""),
    user: dict = Depends(get_current_user),
):
    if not name or len(name) < 2:
        return {"error": "Company name required"}
    insights = get_company_insights(company_name=name, role=role)
    return insights or {"error": "No data found for this company"}
