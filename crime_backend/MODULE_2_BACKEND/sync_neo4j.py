import asyncio
import logging
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.neo4j_connection import (
    init_neo4j, 
    close_neo4j, 
    sync_offender_to_neo4j, 
    sync_victim_to_neo4j,
    sync_location_to_neo4j,
    create_criminal_relationship,
    create_victim_offender_relationship
)
from app.models.database_models.offender_model import Offender
from app.models.database_models.victim_model import Victim
from app.models.database_models.crime_model import CrimeOffenderLink, CrimeVictimLink, District
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def sync():
    logger.info("Connecting to Neo4j...")
    success = await init_neo4j()
    if not success:
        logger.error("Failed to connect to Neo4j")
        return
        
    async with AsyncSessionLocal() as session:
        logger.info("Fetching Offenders from PostgreSQL...")
        result = await session.execute(select(Offender))
        offenders = result.scalars().all()
        for o in offenders:
            await sync_offender_to_neo4j({
                "offender_id": str(o.offender_id),
                "name": f"{o.first_name} {o.last_name}".strip(),
                "risk_level": o.risk_level,
                "risk_score": float(o.risk_score) if o.risk_score else 0.0,
                "crime_count": int(o.total_crimes) if o.total_crimes else 0,
                "status": o.status
            })
        logger.info(f"Synced {len(offenders)} offenders to Neo4j.")
        
        logger.info("Fetching Victims from PostgreSQL...")
        result = await session.execute(select(Victim))
        victims = result.scalars().all()
        for v in victims:
            await sync_victim_to_neo4j({
                "victim_id": str(v.victim_id),
                "name": f"{v.first_name} {v.last_name}".strip(),
                "vulnerability_level": "HIGH" if len(v.vulnerability_factors or []) > 2 else "LOW",
                "victimization_count": v.total_victimizations or 1
            })
        logger.info(f"Synced {len(victims)} victims to Neo4j.")
        
        logger.info("Discovering criminal networks (co-offenders)...")
        result = await session.execute(select(CrimeOffenderLink))
        links = result.scalars().all()
        
        # Group by crime_id
        crimes = {}
        for link in links:
            crime_id_str = str(link.crime_id)
            if crime_id_str not in crimes:
                crimes[crime_id_str] = []
            crimes[crime_id_str].append(str(link.offender_id))
            
        links_created = 0
        for crime_id, offender_ids in crimes.items():
            if len(offender_ids) > 1:
                # Pair them up
                for i in range(len(offender_ids)):
                    for j in range(i + 1, len(offender_ids)):
                        await create_criminal_relationship(
                            offender_id_1=offender_ids[i],
                            offender_id_2=offender_ids[j],
                            relationship_type="WORKED_WITH",
                            strength_score=80.0,
                            confidence_level="CONFIRMED",
                            crime_ids=[crime_id]
                        )
                        links_created += 1
                        
        logger.info(f"Created {links_created} criminal network links based on shared crimes.")
        
        logger.info("Syncing locations and discovering OPERATES_IN networks...")
        result = await session.execute(select(District))
        districts = result.scalars().all()
        for d in districts:
            await sync_location_to_neo4j({
                "location_id": str(d.district_id),
                "name": d.district_name,
                "location_type": "DISTRICT",
                "risk_score": 50,
                "is_hotspot": False
            })
            
        district_groups = defaultdict(list)
        for o in offenders:
            if o.district_id:
                district_groups[o.district_id].append(str(o.offender_id))
        
        for district_id, offender_ids in district_groups.items():
            # Link criminal to location
            for oid in offender_ids:
                query = """
                MATCH (c:Criminal {offender_id: $offender_id})
                MATCH (l:Location {location_id: $location_id})
                MERGE (c)-[r:OPERATES_IN]->(l)
                SET r.confidence_level = 'CONFIRMED'
                """
                from app.core.neo4j_connection import run_neo4j_query
                await run_neo4j_query(query, {"offender_id": oid, "location_id": str(district_id)})
                
            # Inter-criminal links within district
            if len(offender_ids) > 1:
                for i in range(len(offender_ids)):
                    for j in range(i + 1, min(i + 4, len(offender_ids))):  # cap fan-out
                        await create_criminal_relationship(
                            offender_id_1=offender_ids[i],
                            offender_id_2=offender_ids[j],
                            relationship_type="OPERATES_IN",
                            strength_score=40.0,
                            confidence_level="SUSPECTED",
                        )

        logger.info("Discovering victim-offender connections...")
        result = await session.execute(select(CrimeVictimLink))
        victim_links = result.scalars().all()
        crime_to_victims = defaultdict(list)
        for vl in victim_links:
            crime_to_victims[str(vl.crime_id)].append(str(vl.victim_id))

        victims_linked = 0
        for crime_id, offender_ids in crimes.items():
            for victim_id in crime_to_victims.get(crime_id, []):
                for offender_id in offender_ids:
                    await create_victim_offender_relationship(
                        offender_id, victim_id, crime_id
                    )
                    victims_linked += 1
        logger.info(f"Created {victims_linked} victim-offender links.")

    await close_neo4j()
    logger.info("Sync fully complete!")

if __name__ == "__main__":
    asyncio.run(sync())
