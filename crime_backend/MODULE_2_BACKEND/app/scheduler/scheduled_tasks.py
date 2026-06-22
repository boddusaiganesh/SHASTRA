import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.core.database import AsyncSessionLocal
from app.ml_models.anomaly_detection import run_full_anomaly_scan
from app.ml_models.crime_forecasting import forecast_crimes
from app.models.database_models.anomaly_model import Anomaly
from app.models.database_models.prediction_model import Prediction
from app.models.database_models.crime_model import Crime

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
            sixty_days_ago = datetime.utcnow() - timedelta(days=60)
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

def init_scheduler():
    """Initialize and start the background scheduler."""
    try:
        scheduler.add_job(
            run_anomaly_detection,
            trigger=IntervalTrigger(hours=1),
            id="anomaly_detection_job",
            replace_existing=True,
        )
        
        scheduler.add_job(
            run_crime_forecasting,
            trigger=IntervalTrigger(days=1),
            id="crime_forecasting_job",
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
