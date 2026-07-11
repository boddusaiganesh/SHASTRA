"""
Prediction Service - Risk scoring, forecasting, and predictive analytics
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import Optional, Dict, Any
from datetime import datetime, timezone, date, timedelta
import logging

from app.models.database_models.crime_model import Crime, District
from app.models.database_models.location_model import Hotspot
from app.core.redis_connection import cache_get, cache_set

logger = logging.getLogger(__name__)

# Risk level colors
RISK_COLORS = {
    "HIGH": "#ef4444",
    "MEDIUM": "#f97316",
    "LOW": "#22c55e",
}


async def get_risk_map(
    db: AsyncSession,
    district_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Get district-level risk scores for the map"""
    
    cache_key = f"risk_map:{district_id}:{date_from}:{date_to}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Get districts
    district_query = select(District)
    if district_id:
        district_query = district_query.where(District.district_id == district_id)
        
    district_result = await db.execute(district_query)
    districts = district_result.scalars().all()
    
    # Get recent predictions or calculate on the fly
    
    district_risks = []
    
    for district in districts:
        # Get crime count for this district in last 30 days
        from datetime import datetime
        thirty_days_ago = date.today() - timedelta(days=30)
        dt_from = datetime.fromisoformat(date_from).date() if date_from else thirty_days_ago
        dt_to = datetime.fromisoformat(date_to).date() if date_to else date.today()
        crime_count_result = await db.execute(
            select(func.count(Crime.crime_id)).where(
                and_(
                    Crime.district_id == district.district_id,
                    Crime.date_of_occurrence >= dt_from,
                    Crime.date_of_occurrence <= dt_to,
                )
            )
        )
        recent_crime_count = crime_count_result.scalar() or 0
        
        # Get hotspot count
        hotspot_count_result = await db.execute(
            select(func.count(Hotspot.hotspot_id)).where(
                and_(
                    Hotspot.district_id == district.district_id,
                    Hotspot.is_active,
                )
            )
        )
        hotspot_count = hotspot_count_result.scalar() or 0
        
        # Get most common crime type
        crime_type_result = await db.execute(
            select(Crime.crime_type, func.count(Crime.crime_id).label("cnt"))
            .where(
                and_(
                    Crime.district_id == district.district_id,
                    Crime.date_of_occurrence >= dt_from,
                    Crime.date_of_occurrence <= dt_to,
                )
            )
            .group_by(Crime.crime_type)
            .order_by(desc("cnt"))
            .limit(1)
        )
        primary_crime_row = crime_type_result.first()
        primary_crime = primary_crime_row[0] if primary_crime_row else "Theft"
        
        # Calculate risk score (simple heuristic)
        risk_score = min(100, recent_crime_count * 2 + hotspot_count * 10)
        
        if risk_score >= 75:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        district_risks.append({
            "district_id": district.district_id,
            "district_name": district.district_name,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_color": RISK_COLORS[risk_level],
            "primary_risk": primary_crime,
            "confidence": 75.0,
            "trend": "STABLE",
            "boundary_geojson": district.boundary_geojson,
            "latitude": district.latitude,
            "longitude": district.longitude,
        })
    
    response = {"district_risks": district_risks}
    await cache_set(cache_key, response, expiry=1800)
    return response


async def get_high_risk_areas(
    db: AsyncSession,
    days_ahead: int = 7,
    district_id: Optional[str] = None,
    limit: int = 5,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Get predicted high-risk areas"""
    
    cache_key = f"high_risk_areas:{days_ahead}:{district_id}:{limit}:{date_from}:{date_to}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Get active hotspots as high-risk candidates
    if date_from or date_to:
        from app.services.hotspot_service import generate_hotspots_from_crimes
        hotspots_data = await generate_hotspots_from_crimes(db, district_id, None, date_from, date_to)
    else:
        query = select(Hotspot).where(Hotspot.is_active)
        if district_id:
            query = query.where(Hotspot.district_id == district_id)
        query = query.order_by(desc(Hotspot.risk_score)).limit(limit * 2)
        result = await db.execute(query)
        hotspots_data = [h.to_dict() for h in result.scalars().all()]
    
    district_result = await db.execute(select(District))
    district_map = {d.district_id: d.district_name for d in district_result.scalars().all()}
    
    predictions = []
    today = date.today()
    
    for rank, hotspot in enumerate(hotspots_data[:limit], start=1):
        # Get contributing factors
        factors = []
        if hotspot.get("crime_count", 0) > 10:
            factors.append(f"High crime concentration ({hotspot.get('crime_count')} incidents)")
        if hotspot.get("trend") == "INCREASING":
            factors.append(f"Increasing trend ({hotspot.get('trend_percentage', 0):.1f}%)")
        if hotspot.get("dominant_crime_type"):
            factors.append(f"Dominant crime type: {hotspot.get('dominant_crime_type')}")
        if hotspot.get("peak_days"):
            factors.append(f"Peak days: {', '.join(hotspot.get('peak_days', [])[:3])}")
        
        # Get similar past events (simplified)
        similar_events = await db.execute(
            select(Crime)
            .where(
                and_(
                    Crime.district_id == hotspot.get("district_id"),
                    Crime.crime_type == hotspot.get("dominant_crime_type"),
                )
            )
            .limit(3)
        )
        similar_crimes = [
            {"crime_type": c.crime_type, "date": str(c.date_of_occurrence), "district": district_map.get(c.district_id, "")}
            for c in similar_events.scalars().all()
        ]
        
        predictions.append({
            "rank": rank,
            "location": hotspot.get("hotspot_name"),
            "district": district_map.get(hotspot.get("district_id"), hotspot.get("district_id")),
            "predicted_crime_type": hotspot.get("dominant_crime_type") or "General Crime",
            "risk_percentage": min(hotspot.get("risk_score", 0), 100),
            "confidence_level": 72.0,
            "prediction_date_range": {
                "from": today.isoformat(),
                "to": (today + timedelta(days=days_ahead)).isoformat(),
            },
            "recommended_action": hotspot.get("deployment_suggestion") or "Increase patrol frequency",
            "contributing_factors": factors,
            "similar_past_events": similar_crimes,
        })
    
    response = {"predictions": predictions}
    await cache_set(cache_key, response, expiry=3600)
    return response


async def get_crime_forecast(
    db: AsyncSession,
    district_id: Optional[str] = None,
    crime_type: Optional[str] = None,
    days_ahead: int = 30,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Get crime count forecast using Prophet time series model"""
    from app.ml_models.crime_forecasting import forecast_crimes
    
    cache_key = f"crime_forecast:{district_id}:{crime_type}:{days_ahead}:{date_from}:{date_to}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Get historical daily crime counts
    query = select(
        Crime.date_of_occurrence,
        func.count(Crime.crime_id).label("count")
    )
    
    conditions = []
    if district_id:
        conditions.append(Crime.district_id == district_id)
    if crime_type and crime_type != "ALL":
        conditions.append(Crime.crime_type == crime_type)
    if date_from:
        conditions.append(Crime.date_of_occurrence >= date.fromisoformat(date_from))
    if date_to:
        conditions.append(Crime.date_of_occurrence <= date.fromisoformat(date_to))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.group_by(Crime.date_of_occurrence).order_by(Crime.date_of_occurrence)
    
    result = await db.execute(query)
    historical_rows = result.all()
    
    historical_data = [
        {"date": str(row[0]), "count": row[1]}
        for row in historical_rows
        if row[0] is not None
    ]
    
    # Generate forecast
    forecast_result = forecast_crimes(historical_data, days_ahead)
    
    response = {
        "forecast": forecast_result["forecast"],
        "historical": [{"date": h["date"], "actual": h["count"]} for h in historical_data[-60:]],
        "model_accuracy": forecast_result.get("model_accuracy", 78.5),
        "trend_direction": forecast_result.get("trend_direction", "STABLE"),
        "seasonal_factors": forecast_result.get("seasonal_factors", []),
    }
    
    await cache_set(cache_key, response, expiry=3600)
    return response


async def get_emerging_typologies(
    db: AsyncSession,
    district_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Detect emerging crime typologies"""
    from app.services.gemini_service import get_emerging_typology_explanation
    
    cache_key = f"emerging_typologies:{district_id}:{date_from}:{date_to}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    now = date.today()
    if date_to:
        now = date.fromisoformat(date_to)
    
    if date_from:
        recent_start = date.fromisoformat(date_from)
        days_diff = (now - recent_start).days
        baseline_end = recent_start - timedelta(days=1)
        baseline_start = baseline_end - timedelta(days=days_diff)
    else:
        recent_start = now - timedelta(days=30)
        baseline_start = now - timedelta(days=90)
        baseline_end = now - timedelta(days=31)
    
    from app.core.config import CRIME_TYPES
    
    emerging_types = []
    
    for crime_type in CRIME_TYPES:
        conditions_base = [Crime.crime_type == crime_type]
        if district_id:
            conditions_base.append(Crime.district_id == district_id)
        
        # Recent count
        recent_result = await db.execute(
            select(func.count(Crime.crime_id)).where(
                and_(
                    *conditions_base,
                    Crime.date_of_occurrence >= recent_start,
                )
            )
        )
        recent_count = recent_result.scalar() or 0
        
        # Baseline count (normalized to 30 days)
        baseline_result = await db.execute(
            select(func.count(Crime.crime_id)).where(
                and_(
                    *conditions_base,
                    Crime.date_of_occurrence >= baseline_start,
                    Crime.date_of_occurrence <= baseline_end,
                )
            )
        )
        baseline_count = (baseline_result.scalar() or 0) / 2  # Normalize to 30-day period
        
        # Calculate growth rate
        if baseline_count > 0:
            growth_rate = ((recent_count - baseline_count) / baseline_count) * 100
        elif recent_count > 0:
            growth_rate = 100.0
        else:
            growth_rate = 0.0
        
        # Only include types with significant growth
        if growth_rate >= 20 or recent_count >= 5:
            # Find affected districts
            district_result = await db.execute(
                select(Crime.district_id, func.count(Crime.crime_id).label("cnt"))
                .where(
                    and_(Crime.crime_type == crime_type, Crime.date_of_occurrence >= recent_start)
                )
                .group_by(Crime.district_id)
                .having(func.count(Crime.crime_id) >= 2)
                .limit(5)
            )
            
            all_districts_result = await db.execute(select(District))
            district_map = {d.district_id: d.district_name for d in all_districts_result.scalars().all()}
            
            affected = [
                district_map.get(row[0], row[0])
                for row in district_result.all()
            ]
            
            warning_level = "HIGH" if growth_rate >= 50 else ("MEDIUM" if growth_rate >= 20 else "LOW")
            
            emerging_types.append({
                "crime_type": crime_type,
                "growth_rate": round(growth_rate, 1),
                "first_detected": recent_start.isoformat(),
                "affected_districts": affected,
                "pattern_description": f"{crime_type} incidents increased by {growth_rate:.1f}% compared to baseline",
                "warning_level": warning_level,
                "recent_count": recent_count,
            })
    
    # Sort by growth rate
    emerging_types.sort(key=lambda x: x["growth_rate"], reverse=True)
    
    # Get AI explanation for top emerging types
    for et in emerging_types[:5]:
        ai_exp = await get_emerging_typology_explanation(et)
        et["ai_explanation"] = ai_exp
    
    # Overall intelligence briefing
    overall_intel = await get_emerging_typology_explanation(
        {"emerging_types": emerging_types[:5], "district_id": district_id}
    )
    
    response = {
        "emerging_types": emerging_types,
        "overall_intelligence": overall_intel,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await cache_set(cache_key, response, expiry=3600)
    return response


async def get_socioeconomic_correlation(
    db: AsyncSession,
    district_id: Optional[str] = None,
    factor: str = "all",
) -> Dict[str, Any]:
    """Get socioeconomic factor correlations with crime"""
    from app.services.socioeconomic_service import calculate_correlations, get_overlay_data
    from app.services.gemini_service import get_socioeconomic_ai_analysis
    
    cache_key = f"socioeconomic_correlation:{district_id}:{factor}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Get overlay data combining crime and socioeconomic data
    overlay_data = await get_overlay_data(db, district_id)
    
    # Calculate correlations
    correlations = await calculate_correlations(db, district_id, factor)
    
    # Get AI analysis
    ai_analysis = await get_socioeconomic_ai_analysis(correlations, overlay_data)
    
    response = {
        "correlations": correlations,
        "overlay_data": overlay_data,
        "ai_analysis": ai_analysis,
    }
    
    await cache_set(cache_key, response, expiry=3600)
    return response
