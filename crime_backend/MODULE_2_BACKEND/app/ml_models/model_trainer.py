"""
Model Trainer - Retrains ML models with latest data
Called by the scheduler for periodic model updates
"""

import logging
import os
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


async def retrain_all_models(db):
    """Retrain all ML models with latest data"""
    logger.info("Starting model retraining process...")
    
    results = {}
    
    # Retrain risk scoring model
    try:
        results["risk_scoring"] = await retrain_risk_scoring_model(db)
    except Exception as e:
        logger.error(f"Risk scoring model retraining failed: {e}")
        results["risk_scoring"] = "failed"
    
    logger.info(f"Model retraining complete: {results}")
    return results


async def retrain_risk_scoring_model(db) -> str:
    """Retrain the risk scoring random forest model"""
    from sqlalchemy import select, func, and_
    from app.models.database_models.crime_model import Crime, District
    from app.models.database_models.location_model import Hotspot, SocioeconomicData
    from app.ml_models.risk_scoring import train_random_forest_model
    
    logger.info("Retraining risk scoring model...")
    
    today = date.today()
    one_year_ago = today - timedelta(days=365)
    
    district_result = await db.execute(select(District))
    districts = district_result.scalars().all()
    
    training_data = []
    
    for district in districts:
        # Crime rate
        crime_count_result = await db.execute(
            select(func.count(Crime.crime_id)).where(
                and_(
                    Crime.district_id == district.district_id,
                    Crime.date_of_occurrence >= one_year_ago,
                )
            )
        )
        crime_count = crime_count_result.scalar() or 0
        population = district.population or 1000000
        crime_rate = (crime_count / population) * 100000
        
        # Hotspot count
        hotspot_result = await db.execute(
            select(func.count(Hotspot.hotspot_id)).where(
                and_(
                    Hotspot.district_id == district.district_id,
                    Hotspot.is_active == True,
                )
            )
        )
        hotspot_count = hotspot_result.scalar() or 0
        
        # Socioeconomic data
        socio_result = await db.execute(
            select(SocioeconomicData)
            .where(SocioeconomicData.district_id == district.district_id)
            .order_by(SocioeconomicData.year.desc())
            .limit(1)
        )
        socio = socio_result.scalar_one_or_none()
        
        # Determine risk level based on current score
        risk_level = "HIGH" if crime_rate > 50 else ("MEDIUM" if crime_rate > 20 else "LOW")
        
        training_data.append({
            "historical_crime_rate": crime_rate,
            "unemployment_rate": socio.unemployment_rate if socio else 7.5,
            "poverty_index": socio.poverty_index if socio else 18.0,
            "population_density": socio.population_density if socio else (population / (district.total_area_sqkm or 1000)),
            "hotspot_count": hotspot_count,
            "urbanization_rate": socio.urbanization_rate if socio else 45.0,
            "young_male_population": socio.young_male_population if socio else 15.0,
            "cctv_coverage": socio.cctv_coverage if socio else 20.0,
            "street_lighting_coverage": socio.street_lighting_coverage if socio else 60.0,
            "risk_level": risk_level,
        })
    
    if len(training_data) < 10:
        logger.warning("Insufficient training data for risk scoring model")
        return "skipped"
    
    result = train_random_forest_model(training_data)
    
    if result:
        logger.info(f"Risk scoring model trained with accuracy: {result.get('accuracy', 0):.2%}")
        return f"success (accuracy: {result.get('accuracy', 0):.2%})"
    else:
        return "failed"
