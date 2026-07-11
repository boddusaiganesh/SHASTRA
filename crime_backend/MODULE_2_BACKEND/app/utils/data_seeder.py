import logging
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
import uuid
import random

from app.models.database_models.user_model import User
from app.models.database_models.crime_model import District, PoliceStation, Crime, CrimeOffenderLink, CrimeVictimLink
from app.models.database_models.offender_model import Offender
from app.models.database_models.victim_model import Victim
from app.core.security import hash_password
from app.core.config import settings

logger = logging.getLogger(__name__)

async def seed_all_data(session: AsyncSession):
    """Seed initial data for testing the application."""
    try:
        import os
        
        seed_password = getattr(settings, 'SEED_ADMIN_PASSWORD', None) or os.getenv("SEED_ADMIN_PASSWORD")
        if getattr(settings, 'ENVIRONMENT', 'development') == "production" and not seed_password:
            raise RuntimeError("SEED_ADMIN_PASSWORD must be set before seeding in production")
        seed_password = seed_password or "Admin@1234"  # dev-only fallback
        
        admin_user = User(
            user_id=uuid.uuid4(),
            username="admin",
            email="admin@ksp.gov.in",
            password_hash=hash_password(seed_password),
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
        logger.warning("Admin user seeded. Please remember to change the default password!")
        
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
        
        # Seed 5000 Crimes with clusters
        logger.info("Generating 5000 crimes...")
        # High density districts for clustering (Bengaluru Urban, Mysuru, Dakshina Kannada)
        high_density_districts = ["KA-01", "KA-03", "KA-08"]
        crimes_list = []
        
        for i in range(5000):
            # 60% chance to be in a high density district
            if random.random() < 0.6:
                d_choice = random.choice(high_density_districts)
            else:
                d_choice = random.choice(district_ids)
                
            s_choice = station_map.get(d_choice) or station_map[district_ids[0]]
            d_obj = next((d for d in districts if d.district_id == d_choice), districts[0])
            
            # Spread across the past 90 days, with 30% chance to be very recent
            if random.random() < 0.3:
                base_date = date.today() - timedelta(days=random.randint(0, 10))
            else:
                base_date = date.today() - timedelta(days=random.randint(0, 90))
            
            # Spatial clustering: 50% chance to be tightly clustered around headquarters
            if random.random() < 0.5:
                lat_offset = random.uniform(-0.02, 0.02)
                lon_offset = random.uniform(-0.02, 0.02)
            else:
                lat_offset = random.uniform(-0.15, 0.15)
                lon_offset = random.uniform(-0.15, 0.15)
            
            c = Crime(
                crime_reference_no=f"CR-{base_date.year}-{i+1000}",
                crime_type=random.choice(CRIME_TYPES),
                date_of_occurrence=base_date,
                district_id=d_choice,
                police_station_id=s_choice,
                latitude=d_obj.latitude + lat_offset,
                longitude=d_obj.longitude + lon_offset,
                address=f"Sector {random.randint(1, 20)}, {d_obj.district_name}",
                status=random.choice(CRIME_STATUS_VALUES)
            )
            crimes_list.append(c)
            session.add(c)
            
        await session.flush()
        
        logger.info("Generating 100 offenders and 100 victims...")
        first_names = ["Rajan", "Suresh", "Mohammad", "Ramesh", "Ajay", "Venkat", "Kiran", "Vikram", "Arun", "Sanjay"]
        last_names = ["Mehta", "Naik", "Ilyas", "Gowda", "Shetty", "Reddy", "Kumar", "Singh", "Patil", "Rao"]
        v_first_names = ["Priya", "Karim", "Anita", "Ravi", "Meena", "Rahul", "Sneha", "Karthik", "Lakshmi", "Vijay"]

        offenders_list = []
        for i in range(100):
            o = Offender(
                offender_id=uuid.uuid4(),
                offender_reference=f"OFF-{date.today().year}-{i+1000}",
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                age=random.randint(18, 65),
                gender="Male",
                status=random.choice(["ACTIVE", "IMPRISONED", "ABSCONDING"]),
                risk_level=random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
                risk_score=random.uniform(30.0, 95.0),
                district_id=random.choice(district_ids),
                total_crimes=random.randint(1, 15)
            )
            offenders_list.append(o)
        session.add_all(offenders_list)
        
        victims_list = []
        for i in range(100):
            v = Victim(
                victim_id=uuid.uuid4(),
                first_name=random.choice(v_first_names),
                last_name=random.choice(last_names),
                age=random.randint(12, 80),
                gender=random.choice(["Male", "Female"]),
                district_id=random.choice(district_ids)
            )
            victims_list.append(v)
        session.add_all(victims_list)
        await session.flush()

        logger.info("Linking offenders and victims to crimes...")
        NUM_GANGS = 12
        gang_of = {}
        for o in offenders_list:
            gang_of[o.offender_id] = random.randint(0, NUM_GANGS - 1)

        gang_shared_crime = {g: random.sample(crimes_list, k=15) for g in range(NUM_GANGS)}

        for o in offenders_list:
            gang = gang_of[o.offender_id]
            for _ in range(random.randint(2, 6)):
                if random.random() < 0.8:
                    c = random.choice(gang_shared_crime[gang])
                else:
                    c = random.choice(crimes_list)
                session.add(CrimeOffenderLink(
                    crime_id=c.crime_id,
                    offender_id=o.offender_id,
                    role_in_crime=random.choice(["Principal", "Accessory", "Conspirator"]),
                    is_confirmed=True
                ))
        
        for v in victims_list:
            for _ in range(random.randint(1, 2)):
                c = random.choice(crimes_list)
                session.add(CrimeVictimLink(
                    crime_id=c.crime_id,
                    victim_id=v.victim_id
                ))
                
        await session.commit()
        logger.info("Successfully seeded users, districts, stations, crimes, offenders, and victims.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error seeding data: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    from app.core.database import AsyncSessionLocal
    
    async def run_seeder():
        async with AsyncSessionLocal() as session:
            await seed_all_data(session)
            
    asyncio.run(run_seeder())
