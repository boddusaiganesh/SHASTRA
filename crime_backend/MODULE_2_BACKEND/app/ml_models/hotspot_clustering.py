"""
Hotspot Clustering - DBSCAN Algorithm
Identifies crime hotspots using density-based spatial clustering
"""

import numpy as np
from typing import List, Dict, Any
from collections import Counter
import logging

logger = logging.getLogger(__name__)


def run_hotspot_clustering(
    crime_data: List[Dict[str, Any]],
    eps_km: float = 0.5,
    min_samples: int = 3,
) -> List[Dict[str, Any]]:
    """
    Run DBSCAN clustering on crime data to identify hotspots
    
    Args:
        crime_data: List of crime dicts with latitude, longitude, crime_type, etc.
        eps_km: DBSCAN epsilon in kilometers
        min_samples: Minimum crimes to form a cluster
    
    Returns:
        List of hotspot cluster dictionaries
    """
    
    if not crime_data or len(crime_data) < min_samples:
        logger.info("Insufficient crime data for clustering")
        return []
    
    try:
        from sklearn.cluster import DBSCAN
        from sklearn.preprocessing import StandardScaler
        
        # Extract coordinates
        coords = np.array([
            [c["latitude"], c["longitude"]]
            for c in crime_data
            if c.get("latitude") and c.get("longitude")
        ])
        
        if len(coords) < min_samples:
            return []
        
        # Convert epsilon from km to radians for haversine metric
        eps_rad = eps_km / 6371.0  # Earth's radius in km
        
        # Run DBSCAN with haversine distance
        db = DBSCAN(
            eps=eps_rad,
            min_samples=min_samples,
            algorithm='ball_tree',
            metric='haversine',
        )
        
        coords_rad = np.radians(coords)
        labels = db.fit_predict(coords_rad)
        
        # Process clusters
        unique_labels = set(labels)
        unique_labels.discard(-1)  # Remove noise label
        
        hotspots = []
        
        for cluster_id in unique_labels:
            cluster_mask = labels == cluster_id
            cluster_crimes = [crime_data[i] for i, m in enumerate(cluster_mask) if m and i < len(crime_data)]
            cluster_coords = coords[cluster_mask]
            
            if len(cluster_crimes) == 0:
                continue
            
            # Calculate cluster center
            center_lat = float(np.mean(cluster_coords[:, 0]))
            center_lon = float(np.mean(cluster_coords[:, 1]))
            
            # Calculate radius (max distance from center)
            max_dist = 0
            for coord in cluster_coords:
                dist = haversine_distance(center_lat, center_lon, coord[0], coord[1])
                max_dist = max(max_dist, dist)
            
            radius_m = max(max_dist * 1000, 200)  # Minimum 200m radius
            
            # Dominant crime type
            crime_types = Counter([c.get("crime_type", "Unknown") for c in cluster_crimes])
            dominant_type = crime_types.most_common(1)[0][0] if crime_types else "Mixed"
            
            # Crime count
            crime_count = len(cluster_crimes)
            
            # Calculate risk score
            risk_score = calculate_cluster_risk_score(
                crime_count=crime_count,
                crime_types=crime_types,
                cluster_crimes=cluster_crimes,
            )
            
            # Risk level
            if risk_score >= 75:
                risk_level = "HIGH"
            elif risk_score >= 40:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            
            # Time analysis
            time_data = [c.get("time", "12:00") for c in cluster_crimes if c.get("time")]
            peak_time = analyze_peak_time(time_data)
            
            # Day analysis
            from datetime import datetime
            dates = [c.get("date") for c in cluster_crimes if c.get("date")]
            peak_days = analyze_peak_days(dates)
            
            # District (most common)
            districts = Counter([c.get("district_id", "") for c in cluster_crimes])
            district_id = districts.most_common(1)[0][0] if districts else ""
            
            # Generate boundary GeoJSON (circular approximation)
            boundary = create_circle_geojson(center_lat, center_lon, radius_m)
            
            hotspot = {
                "hotspot_id": f"cluster_{cluster_id}",
                "hotspot_name": f"Hotspot Zone {cluster_id + 1} - {dominant_type}",
                "district_id": district_id,
                "center_latitude": center_lat,
                "center_longitude": center_lon,
                "radius_meters": round(radius_m, 0),
                "boundary_geojson": boundary,
                "crime_count": crime_count,
                "dominant_crime_type": dominant_type,
                "risk_level": risk_level,
                "risk_score": round(risk_score, 1),
                "peak_time_start": peak_time.get("start", "20:00"),
                "peak_time_end": peak_time.get("end", "02:00"),
                "peak_days": peak_days[:3],
                "trend": "STABLE",
                "trend_percentage": 0.0,
                "deployment_suggestion": generate_deployment_suggestion(risk_level, dominant_type, peak_time),
                "is_active": True,
                "detected_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            }
            
            hotspots.append(hotspot)
        
        # Sort by risk score descending
        hotspots.sort(key=lambda x: x["risk_score"], reverse=True)
        
        logger.info(f"DBSCAN clustering identified {len(hotspots)} hotspots from {len(crime_data)} crimes")
        
        return hotspots
        
    except ImportError:
        logger.warning("scikit-learn not available, using simple clustering fallback")
        return simple_grid_clustering(crime_data, min_samples)
    except Exception as e:
        logger.error(f"Clustering error: {e}")
        return simple_grid_clustering(crime_data, min_samples)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate haversine distance in km between two points"""
    import math
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def calculate_cluster_risk_score(
    crime_count: int,
    crime_types: Counter,
    cluster_crimes: List[Dict],
) -> float:
    """Calculate risk score for a crime cluster"""
    
    # Base score from crime count
    base_score = min(crime_count * 8, 60)
    
    # Severity bonus
    HIGH_SEVERITY_CRIMES = {"Murder", "Kidnapping", "Sexual Offense", "Robbery"}
    MEDIUM_SEVERITY_CRIMES = {"Assault", "Drug Offense", "Burglary", "Vehicle Theft"}
    
    severity_bonus = 0
    for crime_type, count in crime_types.items():
        if crime_type in HIGH_SEVERITY_CRIMES:
            severity_bonus += count * 5
        elif crime_type in MEDIUM_SEVERITY_CRIMES:
            severity_bonus += count * 2
    
    # Severity cap
    severity_bonus = min(severity_bonus, 30)
    
    # Explicit severity field bonus
    explicit_severity = Counter([c.get("severity", "MEDIUM") for c in cluster_crimes])
    severity_modifier = (
        explicit_severity.get("CRITICAL", 0) * 4 +
        explicit_severity.get("HIGH", 0) * 2 +
        explicit_severity.get("MEDIUM", 0) * 1
    )
    severity_modifier = min(severity_modifier, 10)
    
    total_score = base_score + severity_bonus + severity_modifier
    return min(total_score, 100.0)


def analyze_peak_time(time_data: List[str]) -> Dict[str, str]:
    """Analyze peak crime time from a list of time strings"""
    
    if not time_data:
        return {"start": "20:00", "end": "02:00"}
    
    hours = []
    for t in time_data:
        try:
            hour = int(t.split(":")[0])
            hours.append(hour)
        except:
            pass
    
    if not hours:
        return {"start": "20:00", "end": "02:00"}
    
    # Find most common hour
    hour_counts = Counter(hours)
    peak_hour = hour_counts.most_common(1)[0][0]
    
    return {
        "start": f"{peak_hour:02d}:00",
        "end": f"{(peak_hour + 4) % 24:02d}:00",
    }


def analyze_peak_days(dates: List[str]) -> List[str]:
    """Analyze peak crime days from a list of date strings"""
    from datetime import date
    
    days = []
    for d in dates:
        try:
            dt = date.fromisoformat(d)
            days.append(dt.strftime("%A"))
        except:
            pass
    
    if not days:
        return ["Friday", "Saturday", "Sunday"]
    
    day_counts = Counter(days)
    return [day for day, _ in day_counts.most_common(4)]


def create_circle_geojson(center_lat: float, center_lon: float, radius_m: float) -> Dict:
    """Create a circular GeoJSON polygon approximation"""
    import math
    
    n_points = 16
    coords = []
    
    for i in range(n_points + 1):
        angle = (2 * math.pi * i) / n_points
        dlat = (radius_m / 111320) * math.cos(angle)
        dlon = (radius_m / (111320 * math.cos(math.radians(center_lat)))) * math.sin(angle)
        coords.append([center_lon + dlon, center_lat + dlat])
    
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords],
        },
        "properties": {
            "center_lat": center_lat,
            "center_lon": center_lon,
            "radius_m": radius_m,
        },
    }


def generate_deployment_suggestion(
    risk_level: str,
    crime_type: str,
    peak_time: Dict[str, str],
) -> str:
    """Generate deployment suggestion based on hotspot characteristics"""
    
    time_str = f"{peak_time.get('start', '20:00')} to {peak_time.get('end', '02:00')}"
    
    if risk_level == "HIGH":
        return (
            f"PRIORITY DEPLOYMENT: Station 4-6 officers at this location "
            f"during {time_str}. Implement stop-and-search protocol. "
            f"Focus on {crime_type} prevention. Daily patrol mandatory."
        )
    elif risk_level == "MEDIUM":
        return (
            f"REGULAR PATROL: Assign 2-3 officers for patrol during {time_str}. "
            f"Monitor for {crime_type} activity. Weekly situation reports required."
        )
    else:
        return (
            f"MONITORING: Include in standard patrol routes during {time_str}. "
            f"Alert for {crime_type} indicators. Monthly review."
        )


def simple_grid_clustering(
    crime_data: List[Dict[str, Any]],
    min_samples: int = 3,
) -> List[Dict[str, Any]]:
    """Simple grid-based clustering fallback when sklearn is unavailable"""
    
    from collections import defaultdict
    from datetime import datetime
    
    grid_cells = defaultdict(list)
    
    for crime in crime_data:
        lat = crime.get("latitude", 0)
        lon = crime.get("longitude", 0)
        if lat and lon:
            # Grid at 0.01 degree resolution (~1.1 km)
            grid_lat = round(lat, 2)
            grid_lon = round(lon, 2)
            grid_cells[(grid_lat, grid_lon)].append(crime)
    
    hotspots = []
    cluster_id = 0
    
    for (grid_lat, grid_lon), crimes in grid_cells.items():
        if len(crimes) >= min_samples:
            crime_types = Counter([c.get("crime_type", "Unknown") for c in crimes])
            dominant = crime_types.most_common(1)[0][0]
            
            risk_score = min(len(crimes) * 10, 100.0)
            risk_level = "HIGH" if risk_score >= 75 else ("MEDIUM" if risk_score >= 40 else "LOW")
            
            hotspots.append({
                "hotspot_id": f"grid_{cluster_id}",
                "hotspot_name": f"Crime Cluster {cluster_id + 1} - {dominant}",
                "district_id": crimes[0].get("district_id", ""),
                "center_latitude": grid_lat,
                "center_longitude": grid_lon,
                "radius_meters": 800.0,
                "boundary_geojson": create_circle_geojson(grid_lat, grid_lon, 800),
                "crime_count": len(crimes),
                "dominant_crime_type": dominant,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "peak_time_start": "20:00",
                "peak_time_end": "02:00",
                "peak_days": ["Friday", "Saturday"],
                "trend": "STABLE",
                "trend_percentage": 0.0,
                "deployment_suggestion": generate_deployment_suggestion(risk_level, dominant, {"start": "20:00", "end": "02:00"}),
                "is_active": True,
                "detected_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            })
            cluster_id += 1
    
    hotspots.sort(key=lambda x: x["risk_score"], reverse=True)
    return hotspots
