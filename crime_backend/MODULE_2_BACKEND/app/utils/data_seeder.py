import logging
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date, timezone
import uuid
import random

from app.models.database_models.user_model import User
from app.models.database_models.crime_model import District, PoliceStation, Crime
from app.core.security import hash_password
from app.core.config import settings

logger = logging.getLogger(__name__)

async def seed_all_data(session: AsyncSession):
    """Seed initial data for testing the application."""
    try:
        # Seed a dummy user so the database isn't empty
        admin_user = User(
            user_id=uuid.uuid4(),
            username="admin",
            email="admin@ksp.gov.in",
            password_hash=hash_password("Admin@1234"),
            full_name="System Administrator",
            role="SCRB_OFFICER",
            is_active=True,
            permissions=[
                "view_all_districts", "view_all_crimes", "view_all_offenders",
                "view_network_analysis", "view_predictions", "view_anomalies",
                "view_alerts", "generate_reports", "manage_users",
                "view_settings", "modify_settings"
            ]
        )
        session.add(admin_user)
        
        from app.core.config import KARNATAKA_DISTRICTS, CRIME_TYPES, CRIME_STATUS_VALUES
        from datetime import timedelta

        # Seed all 31 Districts and 1 Police Station per district
        districts = []
        stations = []
        district_ids = []
        station_map = {} # maps district_id -> station_id
        
        for idx, d_data in enumerate(KARNATAKA_DISTRICTS):
            d_id = d_data["district_id"]
            district_ids.append(d_id)
            # Base latitude and longitude for Karnataka (approx 12-18 N, 74-78 E)
            base_lat = 15.3173 + random.uniform(-2, 2)
            base_lon = 75.7139 + random.uniform(-1.5, 1.5)
            
            district = District(
                district_id=d_id,
                district_name=d_data["district_name"],
                district_code=d_data["district_code"],
                headquarters=d_data["headquarters"],
                latitude=base_lat,
                longitude=base_lon
            )
            districts.append(district)
            
            s_id = f"PS_{d_data['district_code']}_01"
            station = PoliceStation(
                station_id=s_id,
                station_name=f"{d_data['headquarters']} Central PS",
                district_id=d_id,
                latitude=base_lat + random.uniform(-0.01, 0.01),
                longitude=base_lon + random.uniform(-0.01, 0.01)
            )
            stations.append(station)
            station_map[d_id] = s_id
            
        session.add_all(districts)
        session.add_all(stations)
        await session.flush()
        
        # Seed 200 Crimes
        for i in range(200):
            d_choice = random.choice(district_ids)
            s_choice = station_map[d_choice]
            # Find the district's base lat/lon
            d_obj = next(d for d in districts if d.district_id == d_choice)
            
            # Spread across the past 90 days
            base_date = date.today() - timedelta(days=random.randint(0, 90))
            
            c = Crime(
                crime_reference_no=f"CR-{base_date.year}-{i+1000}",
                crime_type=random.choice(CRIME_TYPES),
                date_of_occurrence=base_date,
                district_id=d_choice,
                police_station_id=s_choice,
                latitude=d_obj.latitude + random.uniform(-0.05, 0.05),
                longitude=d_obj.longitude + random.uniform(-0.05, 0.05),
                address=f"Street {random.randint(1, 100)}, {d_obj.district_name}",
                status=random.choice(CRIME_STATUS_VALUES)
            )
            session.add(c)
            
        await session.commit()
        logger.info("Successfully seeded users, districts, stations, and crimes.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error seeding data: {e}")
        raise
