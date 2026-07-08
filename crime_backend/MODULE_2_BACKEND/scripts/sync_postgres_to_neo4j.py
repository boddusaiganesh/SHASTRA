import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

# We run this in the container, so we have access to the app modules
from app.core.database import Base
from app.models.database_models.offender_model import Offender
from app.models.database_models.victim_model import Victim
from app.models.database_models.location_model import Location
from app.models.database_models.crime_model import Crime, CrimeOffenderLink, CrimeVictimLink

from app.core.neo4j_connection import (
    sync_offender_to_neo4j,
    sync_victim_to_neo4j,
    sync_location_to_neo4j,
    create_criminal_relationship,
    create_victim_offender_relationship,
    _create_indexes,
    init_neo4j,
    close_neo4j
)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("No DATABASE_URL found. Exiting.")
    sys.exit(1)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def sync_data():
    print("Starting sync from PostgreSQL to Neo4j...")
    
    await init_neo4j()
    # Ensure indexes exist
    await _create_indexes()

    async with AsyncSessionLocal() as db:
        print("Fetching crimes and links to calculate crime_types...")
        crimes = (await db.execute(select(Crime))).scalars().all()
        crime_map = {str(c.crime_id): c for c in crimes}
        
        victim_links = (await db.execute(select(CrimeVictimLink))).scalars().all()
        offender_links = (await db.execute(select(CrimeOffenderLink))).scalars().all()
        
        # Group by crime
        crime_to_victims = {}
        for vl in victim_links:
            cid = str(vl.crime_id)
            crime_to_victims.setdefault(cid, []).append(str(vl.victim_id))
            
        crime_to_offenders = {}
        for ol in offender_links:
            cid = str(ol.crime_id)
            crime_to_offenders.setdefault(cid, []).append(str(ol.offender_id))

        # Sync Offenders
        print("Syncing offenders...")
        offenders = (await db.execute(select(Offender))).scalars().all()
        for off in offenders:
            off_crime_types = list({
                crime_map[cid].crime_type
                for cid, oids in crime_to_offenders.items() if str(off.offender_id) in oids
            })
            await sync_offender_to_neo4j({
                "offender_id": str(off.offender_id),
                "name": f"{off.first_name} {off.last_name}",
                "risk_level": off.risk_level,
                "risk_score": off.risk_score or 0,
                "crime_count": off.total_crimes or 0,
                "status": off.status,
                "district_id": off.district_id,
                "crime_types": off_crime_types,
            })
        print(f"Synced {len(offenders)} offenders.")

        # Sync Victims
        print("Syncing victims...")
        victims = (await db.execute(select(Victim))).scalars().all()
        for vic in victims:
            vic_crime_types = list({
                crime_map[cid].crime_type
                for cid, vids in crime_to_victims.items() if str(vic.victim_id) in vids
            })
            await sync_victim_to_neo4j({
                "victim_id": str(vic.victim_id),
                "name": f"{vic.first_name} {vic.last_name}",
                "vulnerability_level": len(vic.vulnerability_factors) * 10 if vic.vulnerability_factors else 0,
                "victimization_count": vic.total_victimizations or 1,
                "district_id": vic.district_id,
                "crime_types": vic_crime_types,
            })
        print(f"Synced {len(victims)} victims.")

        # Sync Locations
        print("Syncing locations...")
        locations = (await db.execute(select(Location))).scalars().all()
        for loc in locations:
            await sync_location_to_neo4j({
                "location_id": str(loc.location_id),
                "name": loc.location_name,
                "location_type": loc.location_type,
                "risk_score": loc.risk_score or 0,
                "is_hotspot": loc.is_hotspot,
                "district_id": loc.district_id,
            })
        print(f"Synced {len(locations)} locations.")

        # Create Relationships - Criminal to Criminal
        print("Creating criminal relationships...")
        rels_count = 0
        for off in offenders:
            node_id = str(off.offender_id)
            if off.known_associates:
                off_crime_types = list({
                    crime_map[cid].crime_type
                    for cid, oids in crime_to_offenders.items() if str(off.offender_id) in oids
                })
                for associate_id in off.known_associates:
                    await create_criminal_relationship(
                        offender_id_1=node_id,
                        offender_id_2=associate_id,
                        relationship_type="KNOWS",
                        strength_score=60.0,
                        confidence_level="SUSPECTED",
                        crime_ids=[],
                        crime_types=off_crime_types
                    )
                    rels_count += 1
        print(f"Created {rels_count} criminal relationships.")

        # Create Relationships - Victim to Criminal
        print("Creating victim-offender relationships...")
        vo_count = 0
        for cid, crime in crime_map.items():
            if cid in crime_to_offenders and cid in crime_to_victims:
                for oid in crime_to_offenders[cid]:
                    for vid in crime_to_victims[cid]:
                        await create_victim_offender_relationship(
                            offender_id=oid,
                            victim_id=vid,
                            crime_id=cid,
                            crime_type=crime.crime_type
                        )
                        vo_count += 1
        print(f"Created {vo_count} victim-offender relationships.")

    await close_neo4j()
    print("Sync complete.")

if __name__ == "__main__":
    asyncio.run(sync_data())
