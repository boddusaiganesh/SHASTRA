import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sqlalchemy import select, func, delete
from datetime import datetime, timedelta, timezone

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.ml_models.anomaly_detection import run_full_anomaly_scan
from app.ml_models.crime_forecasting import forecast_crimes
from app.models.database_models.anomaly_model import Anomaly
from app.models.database_models.prediction_model import Prediction
from app.models.database_models.crime_model import Crime
from app.models.database_models.location_model import Hotspot
from app.ml_models.model_trainer import retrain_all_models
from app.services.alert_service import detect_and_generate_alerts, cleanup_expired_alerts
from app.services.hotspot_service import generate_hotspots_from_crimes

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_anomaly_detection():
    logger.info("Running background anomaly detection (Isolation Forest)...")
    try:
        async with AsyncSessionLocal() as db:
            anomalies = await run_full_anomaly_scan(db)
            if anomalies:
                for anomaly_data in anomalies:
                    anomaly = Anomaly(
                        anomaly_type=anomaly_data["anomaly_type"],
                        severity=anomaly_data["severity"],
                        district_id=anomaly_data["district_id"],
                        description=anomaly_data["description"],
                        evidence_points=anomaly_data["evidence_points"],
                        anomaly_score=anomaly_data["anomaly_score"],
                        ai_explanation="Detected via ML Isolation Forest algorithm.",
                    )
                    db.add(anomaly)
                await db.commit()
                logger.info(f"Saved {len(anomalies)} anomalies to database.")
    except Exception as e:
        logger.error(f"Error in anomaly detection task: {e}")


async def run_crime_forecasting():
    logger.info("Running background crime forecasting (Facebook Prophet)...")
    try:
        async with AsyncSessionLocal() as db:
            sixty_days_ago = datetime.now(timezone.utc) - timedelta(days=60)
            result = await db.execute(
                select(
                    func.date(Crime.date_of_occurrence).label('date'),
                    func.count(Crime.crime_id).label('count')
                )
                .where(Crime.date_of_occurrence >= sixty_days_ago)
                .group_by(func.date(Crime.date_of_occurrence))
                .order_by(func.date(Crime.date_of_occurrence))
            )
            
            historical_data = []
            for row in result.all():
                historical_data.append({"date": str(row[0]), "count": row[1]})
            
            forecast_result = forecast_crimes(historical_data, days_ahead=30)
            
            prediction = Prediction(
                prediction_type="STATE_WIDE_FORECAST",
                predicted_crime_type="ALL",
                model_used="Facebook Prophet",
                accuracy_score=forecast_result.get("model_accuracy", 0.0),
                forecast_data=forecast_result,
            )
            db.add(prediction)
            await db.commit()
            logger.info("Saved new 30-day crime forecast to database.")
            
    except Exception as e:
        logger.error(f"Error in crime forecasting task: {e}")


async def run_model_retraining():
    logger.info("Running scheduled ML model retraining...")
    try:
        async with AsyncSessionLocal() as db:
            results = await retrain_all_models(db)
            logger.info(f"Model retraining results: {results}")
    except Exception as e:
        logger.error(f"Error in model retraining task: {e}")


async def run_alert_detection():
    logger.info("Running background alert detection (Crime Spikes)...")
    try:
        async with AsyncSessionLocal() as db:
            await detect_and_generate_alerts(db)
    except Exception as e:
        logger.error(f"Error in alert detection task: {e}")


async def run_alert_cleanup():
    logger.info("Running background alert database cleanup...")
    try:
        async with AsyncSessionLocal() as db:
            await cleanup_expired_alerts(db)
    except Exception as e:
        logger.error(f"Error in alert cleanup task: {e}")


async def run_hotspot_regeneration():
    logger.info("Running background hotspot regeneration (DBSCAN)...")
    try:
        async with AsyncSessionLocal() as db:
            # Clear old active hotspots
            await db.execute(delete(Hotspot))
            
            # Generate new hotspots across all districts
            hotspots_data = await generate_hotspots_from_crimes(db)
            
            for hd in hotspots_data:
                hotspot = Hotspot(
                    hotspot_name=hd["hotspot_name"],
                    district_id=hd["district_id"],
                    center_latitude=hd["center_latitude"],
                    center_longitude=hd["center_longitude"],
                    radius_meters=hd["radius_meters"],
                    boundary_geojson=hd["boundary_geojson"],
                    crime_count=hd["crime_count"],
                    dominant_crime_type=hd["dominant_crime_type"],
                    risk_level=hd["risk_level"],
                    risk_score=hd["risk_score"],
                    peak_time_start=hd["peak_time_start"],
                    peak_time_end=hd["peak_time_end"],
                    peak_days=hd["peak_days"],
                    trend=hd["trend"],
                    trend_percentage=hd["trend_percentage"],
                    deployment_suggestion=hd["deployment_suggestion"],
                    is_active=hd["is_active"],
                )
                db.add(hotspot)
            
            await db.commit()
            logger.info(f"Successfully regenerated and saved {len(hotspots_data)} hotspots.")
    except Exception as e:
        logger.error(f"Error in hotspot regeneration task: {e}")


async def run_cross_district_mo_matching():
    logger.info("Running cross-district MO matching...")
    try:
        async with AsyncSessionLocal() as db:
            from app.models.database_models.offender_model import Offender
            from app.services.alert_service import create_alert
            from app.services.offender_service import get_offender_history
            from app.ml_models.modus_operandi_analyzer import analyze_modus_operandi, calculate_mo_similarity
            from sqlalchemy import select

            result = await db.execute(select(Offender).where(Offender.total_crimes >= 2))
            offenders = result.scalars().all()
            
            checked_pairs = set()
            for i, off_a in enumerate(offenders):
                for j, off_b in enumerate(offenders[i+1:]):
                    if off_a.district_id == off_b.district_id:
                        continue

                    pair_key = tuple(sorted([str(off_a.offender_id), str(off_b.offender_id)]))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)

                    hist_a = await get_offender_history(db, str(off_a.offender_id))
                    hist_b = await get_offender_history(db, str(off_b.offender_id))
                    
                    if not hist_a or not hist_b or not hist_a.get("crimes") or not hist_b.get("crimes"):
                        continue
                        
                    mo_a = analyze_modus_operandi(hist_a["crimes"], off_a.to_dict())
                    mo_b = analyze_modus_operandi(hist_b["crimes"], off_b.to_dict())

                    similarity = calculate_mo_similarity(mo_a, mo_b)
                    if similarity >= 0.75:  # tune threshold after a real data run
                        await create_alert(
                            db,
                            alert_type="CROSS_DISTRICT_MATCH",
                            severity="HIGH" if similarity >= 0.9 else "MEDIUM",
                            title=f"Possible cross-district match: {off_a.first_name} {off_a.last_name} / {off_b.first_name} {off_b.last_name}",
                            description=(
                                f"Offenders in {off_a.district_id} and {off_b.district_id} share a "
                                f"{similarity*100:.0f}% similar modus operandi (crime type, timing, weapons, "
                                f"behavioral signature). Recommend cross-checking for a shared offender."
                            ),
                            district_id=off_a.district_id,
                            related_entity_id=str(off_a.offender_id),
                            related_entity_type="offender",
                            target_role="SCRB_OFFICER",
                        )
            logger.info(f"Cross-district MO scan complete. Checked {len(checked_pairs)} pairs.")
    except Exception as e:
        logger.error(f"Error in cross-district MO matching task: {e}")




def init_scheduler():
    """Initialize and start the background scheduler."""
    try:
        # 1. Anomaly detection interval
        scheduler.add_job(
            run_anomaly_detection,
            trigger=IntervalTrigger(hours=settings.ANOMALY_SCAN_INTERVAL_HOURS),
            id="anomaly_detection_job",
            replace_existing=True,
        )
        # Run initial anomaly detection immediately on startup
        scheduler.add_job(
            run_anomaly_detection,
            id="anomaly_detection_startup",
            replace_existing=True,
        )
        
        # 2. Crime forecasting - weekly on specified day
        day_str = settings.FORECAST_UPDATE_DAY[:3].lower()
        scheduler.add_job(
            run_crime_forecasting,
            trigger=CronTrigger(day_of_week=day_str, hour=2, minute=30),
            id="crime_forecasting_job",
            replace_existing=True,
        )
        
        # 3. Model retraining - weekly on Sunday at 2 AM
        scheduler.add_job(
            run_model_retraining,
            trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
            id="model_retraining_job",
            replace_existing=True,
        )

        # 4. Alert generation - hourly
        scheduler.add_job(
            run_alert_detection,
            trigger=IntervalTrigger(hours=1),
            id="alert_detection_job",
            replace_existing=True,
        )
        
        # 5. Alert database cleanup - daily
        scheduler.add_job(
            run_alert_cleanup,
            trigger=IntervalTrigger(hours=24),
            id="alert_cleanup_job",
            replace_existing=True,
        )
        
        # 6. Hotspot regeneration - daily at configured hour
        scheduler.add_job(
            run_hotspot_regeneration,
            trigger=CronTrigger(hour=settings.HOTSPOT_UPDATE_HOUR, minute=0),
            id="hotspot_regeneration_job",
            replace_existing=True,
        )

        # 7. Run initial hotspot generation immediately on startup if empty
        scheduler.add_job(
            run_hotspot_regeneration,
            id="hotspot_regeneration_startup",
            replace_existing=True,
        )
        
        # 8. Cross-district MO matching — daily
        scheduler.add_job(
            run_cross_district_mo_matching,
            trigger=CronTrigger(hour=3, minute=0),
            id="cross_district_mo_job",
            replace_existing=True,
        )
        
        scheduler.start()
        logger.info("Background ML scheduler started successfully.")
    except Exception as e:
        logger.error(f"Failed to start ML scheduler: {e}")


def shutdown_scheduler():
    """Shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background ML scheduler shut down.")
