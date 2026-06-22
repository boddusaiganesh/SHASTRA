import logging
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date, timezone
import uuid
import random

from app.models.database_models.user_model import User
from app.models.database_models.crime_model import District, PoliceStation, Crime

logger = logging.getLogger(__name__)

async def seed_all_data(session: AsyncSession):
    """Seed initial data for testing the application."""
    try:
        # Seed a dummy user so the database isn't empty
        admin_user = User(
            user_id=uuid.uuid4(),
            username="admin",
            email="admin@ksp.gov.in",
            hashed_password="hashed_password_mock",
            full_name="System Administrator",
            role="ADMIN",
            is_active=True
        )
        session.add(admin_user)
        
        # Seed Districts
        d1 = District(
            district_id="D01",
            district_name="Bengaluru City",
            district_code="BLR",
            headquarters="Bengaluru",
            latitude=12.9716,
            longitude=77.5946
        )
        d2 = District(
            district_id="D02",
            district_name="Mysuru",
            district_code="MYS",
            headquarters="Mysuru",
            latitude=12.2958,
            longitude=76.6394
        )
        session.add_all([d1, d2])
        
        # Seed Police Stations
        ps1 = PoliceStation(
            station_id="PS_BLR_01",
            station_name="Cubbon Park PS",
            district_id="D01",
            latitude=12.9784,
            longitude=77.5982
        )
        ps2 = PoliceStation(
            station_id="PS_MYS_01",
            station_name="Devaraja PS",
            district_id="D02",
            latitude=12.3052,
            longitude=76.6500
        )
        session.add_all([ps1, ps2])
        
        # Seed Crimes (Mock Map Data)
        crime_types = ["Theft", "Assault", "Burglary", "Cybercrime", "Narcotics"]
        statuses = ["REPORTED", "Under Investigation", "Arrested", "Solved"]
        
        for i in range(10):
            is_blr = random.choice([True, False])
            base_lat = 12.9716 if is_blr else 12.2958
            base_lon = 77.5946 if is_blr else 76.6394
            
            c = Crime(
                crime_reference_no=f"CR-{2026}-{i+1000}",
                crime_type=random.choice(crime_types),
                date_of_occurrence=date(2026, 6, random.randint(1, 20)),
                district_id="D01" if is_blr else "D02",
                police_station_id="PS_BLR_01" if is_blr else "PS_MYS_01",
                latitude=base_lat + random.uniform(-0.05, 0.05),
                longitude=base_lon + random.uniform(-0.05, 0.05),
                address=f"Street {random.randint(1, 50)}, {'Bengaluru' if is_blr else 'Mysuru'}",
                status=random.choice(statuses)
            )
            session.add(c)
            
        await session.commit()
        logger.info("Successfully seeded users, districts, stations, and crimes.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error seeding data: {e}")
        raise
