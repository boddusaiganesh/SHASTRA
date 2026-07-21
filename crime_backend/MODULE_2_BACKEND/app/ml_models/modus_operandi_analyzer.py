"""
Modus Operandi Analyzer - Statistical Pattern Analysis for offender behavior
"""

from typing import List, Dict, Any, Optional
from collections import Counter
import logging

logger = logging.getLogger(__name__)


def analyze_modus_operandi(
    crimes: List[Dict[str, Any]],
    offender_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze an offender's modus operandi from their crime history
    
    Args:
        crimes: List of crime records associated with the offender
        offender_data: Basic offender profile data
    
    Returns:
        Comprehensive MO analysis dictionary
    """
    
    if not crimes:
        return _empty_mo_analysis()
    
    # Crime type analysis
    crime_types = Counter([c.get("crime_type", "Unknown") for c in crimes])
    preferred_types = [
        {
            "crime_type": ct,
            "frequency": cnt,
            "percentage": round(cnt / len(crimes) * 100, 1),
        }
        for ct, cnt in crime_types.most_common()
    ]
    
    # Time pattern analysis
    time_patterns = _analyze_time_patterns(crimes)
    
    # Location pattern analysis
    location_patterns = _analyze_location_patterns(crimes)
    
    # Victim pattern analysis
    victim_patterns = _analyze_victim_patterns(crimes)
    
    # Weapon pattern analysis
    weapon_patterns = _analyze_weapon_patterns(crimes)
    
    # Accomplice pattern
    accomplice_pattern = _analyze_accomplice_pattern(offender_data, crimes)
    
    # Geographic range
    geographic_range = _calculate_geographic_range(crimes)
    
    # Crime interval
    avg_interval = _calculate_crime_interval(crimes)
    
    # Escalation trend
    escalation = _analyze_escalation(crimes)
    
    # Behavioral signatures
    signatures = _identify_behavioral_signatures(crimes, offender_data)
    
    return {
        "total_crimes_analyzed": len(crimes),
        "preferred_crime_types": preferred_types,
        "time_patterns": time_patterns,
        "preferred_locations": location_patterns.get("location_types", []),
        "preferred_time": time_patterns.get("preferred_time_of_day", "UNKNOWN"),
        "preferred_days": time_patterns.get("preferred_days", []),
        "typical_targets": victim_patterns.get("typical_targets", "Unknown"),
        "victim_demographics": victim_patterns,
        "weapons_pattern": weapon_patterns,
        "escape_methods": "Under investigation",
        "accomplice_pattern": accomplice_pattern,
        "average_crime_interval": avg_interval,
        "geographic_range": geographic_range,
        "escalation_trend": escalation,
        "behavioral_signatures": signatures,
    }


def _analyze_time_patterns(crimes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze time patterns in crime history"""
    
    hours = []
    days = []
    
    for crime in crimes:
        time_str = crime.get("time_of_occurrence") or crime.get("time", "")
        if time_str:
            try:
                hour = int(time_str.split(":")[0])
                hours.append(hour)
            except ValueError:
                pass
        
        day = crime.get("day_of_week")
        if day:
            days.append(day)
    
    # Time of day preference
    time_categories = {"MORNING": 0, "AFTERNOON": 0, "EVENING": 0, "NIGHT": 0}
    for h in hours:
        if 6 <= h < 12:
            time_categories["MORNING"] += 1
        elif 12 <= h < 18:
            time_categories["AFTERNOON"] += 1
        elif 18 <= h < 22:
            time_categories["EVENING"] += 1
        else:
            time_categories["NIGHT"] += 1
    
    preferred_time = max(time_categories, key=time_categories.get) if hours else "UNKNOWN"
    
    # Peak hours
    hour_counter = Counter(hours)
    peak_hours = [h for h, _ in hour_counter.most_common(3)]
    
    # Preferred days
    day_counter = Counter(days)
    preferred_days = [
        {"day": d, "count": c}
        for d, c in day_counter.most_common(4)
    ]
    
    return {
        "preferred_time_of_day": preferred_time,
        "time_distribution": time_categories,
        "peak_hours": peak_hours,
        "preferred_days": preferred_days,
        "patterns_detected": len(hours) >= 3,
    }


def _analyze_location_patterns(crimes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze location patterns"""
    
    location_types = []
    districts = Counter()
    
    for crime in crimes:
        loc_type = crime.get("location_type") or _infer_location_type(crime.get("address", ""))
        if loc_type:
            location_types.append(loc_type)
        
        district = crime.get("district") or crime.get("district_id", "")
        if district:
            districts[district] += 1
    
    type_counter = Counter(location_types)
    
    return {
        "location_types": [
            {"type": lt, "count": cnt}
            for lt, cnt in type_counter.most_common(5)
        ],
        "preferred_districts": [
            {"district": d, "count": c}
            for d, c in districts.most_common(3)
        ],
    }


def _infer_location_type(address: str) -> Optional[str]:
    """Infer location type from address string"""
    if not address:
        return None
    
    address_lower = address.lower()
    if any(kw in address_lower for kw in ["market", "shop", "mall", "commercial"]):
        return "COMMERCIAL"
    elif any(kw in address_lower for kw in ["road", "highway", "nh", "sh"]):
        return "HIGHWAY"
    elif any(kw in address_lower for kw in ["park", "garden", "public"]):
        return "PUBLIC"
    elif any(kw in address_lower for kw in ["residential", "colony", "nagar", "layout"]):
        return "RESIDENTIAL"
    return "UNKNOWN"


def _analyze_victim_patterns(crimes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze victim targeting patterns"""
    
    # For crimes that have victim information
    all_victims = []
    for crime in crimes:
        victims = crime.get("victims", [])
        all_victims.extend(victims)
    
    if not all_victims:
        return {
            "typical_targets": "Pattern analysis requires victim data",
            "target_demographics": "Unknown",
        }
    
    genders = Counter([v.get("gender", "Unknown") for v in all_victims])
    age_groups = {"minor": 0, "young_adult": 0, "adult": 0, "elderly": 0}
    
    for v in all_victims:
        age = v.get("age")
        if age is None or age <= 0:
            continue
        if age < 18:
            age_groups["minor"] += 1
        elif age < 30:
            age_groups["young_adult"] += 1
        elif age < 60:
            age_groups["adult"] += 1
        else:
            age_groups["elderly"] += 1
    
    # Dominant gender
    dominant_gender = genders.most_common(1)[0][0] if genders else "Mixed"
    dominant_age = max(age_groups, key=age_groups.get)
    
    typical_targets = f"Primarily {dominant_gender.lower()} {dominant_age.replace('_', ' ')} targets"
    
    return {
        "typical_targets": typical_targets,
        "gender_distribution": dict(genders),
        "age_distribution": age_groups,
        "total_victims_analyzed": len(all_victims),
    }


def _analyze_weapon_patterns(crimes: List[Dict[str, Any]]) -> List[str]:
    """Analyze weapons usage patterns"""
    
    weapons = Counter()
    for crime in crimes:
        crime_weapons = crime.get("weapons_used", [])
        for w in crime_weapons:
            weapons[w] += 1
    
    if not weapons:
        return ["No weapons documented"]
    
    return [f"{w} ({c} times)" for w, c in weapons.most_common(5)]


def _analyze_accomplice_pattern(
    offender_data: Dict[str, Any],
    crimes: List[Dict[str, Any]],
) -> str:
    """Determine if offender typically works alone or with accomplices"""
    
    associates = offender_data.get("known_associates", [])
    
    # Check crimes that had multiple offenders
    group_crimes = sum(
        1 for c in crimes
        if len(c.get("offenders", [])) > 1
    )
    
    if len(associates) >= 3 or group_crimes >= len(crimes) * 0.5:
        return "GROUP"
    elif len(associates) >= 1 or group_crimes >= len(crimes) * 0.2:
        return "WITH_PARTNER"
    else:
        return "SOLO"


def _calculate_geographic_range(crimes: List[Dict[str, Any]]) -> str:
    """Calculate the geographic range of the offender"""
    
    lats = [c.get("latitude") for c in crimes if c.get("latitude")]
    lons = [c.get("longitude") for c in crimes if c.get("longitude")]
    
    if not lats or not lons or len(lats) < 2:
        unique_districts = len(set(c.get("district_id", "") for c in crimes))
        if unique_districts >= 5:
            return "Multi-District"
        elif unique_districts >= 2:
            return "Regional (2-5 districts)"
        else:
            return "Local (single district)"
    
    lat_range = max(lats) - min(lats)
    lon_range = max(lons) - min(lons)
    km_range = ((lat_range ** 2 + lon_range ** 2) ** 0.5) * 111
    
    if km_range > 100:
        return "Wide (> 100 km)"
    elif km_range > 50:
        return "Large Regional (50-100 km)"
    elif km_range > 20:
        return "Regional (20-50 km)"
    elif km_range > 5:
        return "District-wide (5-20 km)"
    else:
        return "Local (< 5 km)"


def _calculate_crime_interval(crimes: List[Dict[str, Any]]) -> int:
    """Calculate average days between crimes"""
    from datetime import date
    
    dates = []
    for c in crimes:
        date_str = c.get("date_of_occurrence") or c.get("date")
        if date_str:
            try:
                dates.append(date.fromisoformat(str(date_str)))
            except ValueError:
                pass
    
    dates.sort()
    
    if len(dates) < 2:
        return 0
    
    intervals = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
    return int(sum(intervals) / len(intervals))


def _analyze_escalation(crimes: List[Dict[str, Any]]) -> str:
    """Determine if crimes are escalating in severity"""
    
    SEVERITY_MAP = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    
    severity_scores = [
        SEVERITY_MAP.get(c.get("severity", "MEDIUM"), 2)
        for c in crimes
    ]
    
    if len(severity_scores) < 3:
        return "INSUFFICIENT_DATA"
    
    early = sum(severity_scores[:len(severity_scores)//3]) / max(len(severity_scores)//3, 1)
    late = sum(severity_scores[-len(severity_scores)//3:]) / max(len(severity_scores)//3, 1)
    
    if late > early * 1.2:
        return "ESCALATING"
    elif late < early * 0.8:
        return "DE_ESCALATING"
    else:
        return "STABLE"


def _identify_behavioral_signatures(
    crimes: List[Dict[str, Any]],
    offender_data: Dict[str, Any],
) -> List[str]:
    """Identify unique behavioral signatures"""
    
    signatures = []
    
    # MO consistency
    crime_types = Counter([c.get("crime_type", "") for c in crimes])
    if crime_types.most_common(1)[0][1] >= len(crimes) * 0.7:
        signatures.append(f"Strong preference for {crime_types.most_common(1)[0][0]}")
    
    # Time consistency
    hours = []
    for c in crimes:
        t = c.get("time_of_occurrence", "")
        if t:
            try:
                hours.append(int(t.split(":")[0]))
            except ValueError:
                pass
    
    if hours:
        avg_hour = sum(hours) / len(hours)
        std_hour = (sum((h - avg_hour)**2 for h in hours) / len(hours)) ** 0.5
        if std_hour < 3:
            signatures.append(f"Highly consistent timing - operates near {int(avg_hour):02d}:00")
    
    # Solo vs group
    if offender_data.get("known_associates"):
        signatures.append(f"Known to operate with {len(offender_data['known_associates'])} associates")
    
    # Repeat jurisdiction
    districts = Counter([c.get("district_id", "") for c in crimes if c.get("district_id")])
    if districts and districts.most_common(1)[0][1] >= len(crimes) * 0.6:
        signatures.append("Strongly territorial - operates primarily in home district")
    
    return signatures


def _empty_mo_analysis() -> Dict[str, Any]:
    """Return empty MO analysis for offenders with no crime history"""
    return {
        "total_crimes_analyzed": 0,
        "preferred_crime_types": [],
        "time_patterns": {},
        "preferred_locations": [],
        "preferred_time": "UNKNOWN",
        "preferred_days": [],
        "typical_targets": "No crime history available",
        "weapons_pattern": [],
        "accomplice_pattern": "UNKNOWN",
        "average_crime_interval": 0,
        "geographic_range": "Unknown",
        "escalation_trend": "INSUFFICIENT_DATA",
        "behavioral_signatures": [],
    }

def calculate_mo_similarity(mo_a: Dict[str, Any], mo_b: Dict[str, Any]) -> float:
    """Calculate a similarity score (0.0 to 1.0) between two Modus Operandi profiles"""
    if not mo_a.get("total_crimes_analyzed") or not mo_b.get("total_crimes_analyzed"):
        return 0.0
        
    score = 0.0
    weights = {
        "crime_type": 0.4,
        "time": 0.2,
        "weapon": 0.2,
        "location": 0.1,
        "accomplice": 0.1
    }
    
    # 1. Crime Type Similarity
    a_types = {t.get("crime_type") for t in mo_a.get("preferred_crime_types", []) if isinstance(t, dict)}
    b_types = {t.get("crime_type") for t in mo_b.get("preferred_crime_types", []) if isinstance(t, dict)}
    if a_types and b_types and len(a_types.intersection(b_types)) > 0:
        score += weights["crime_type"] * (len(a_types.intersection(b_types)) / max(len(a_types), len(b_types)))
        
    # 2. Time Pattern Similarity
    if mo_a.get("preferred_time") == mo_b.get("preferred_time") and mo_a.get("preferred_time") != "UNKNOWN":
        score += weights["time"]
        
    # 3. Weapon Similarity
    a_weapons = set(mo_a.get("weapons_pattern", []))
    b_weapons = set(mo_b.get("weapons_pattern", []))
    if a_weapons and b_weapons and a_weapons != {"No weapons documented"} and b_weapons != {"No weapons documented"}:
        if len(a_weapons.intersection(b_weapons)) > 0:
            score += weights["weapon"]
            
    # 4. Location Type Similarity
    a_locs = {l.get("type") for l in mo_a.get("preferred_locations", []) if isinstance(l, dict)}
    b_locs = {l.get("type") for l in mo_b.get("preferred_locations", []) if isinstance(l, dict)}
    if a_locs and b_locs and len(a_locs.intersection(b_locs)) > 0:
        score += weights["location"]
        
    # 5. Accomplice Pattern
    if mo_a.get("accomplice_pattern") == mo_b.get("accomplice_pattern") and mo_a.get("accomplice_pattern") != "UNKNOWN":
        score += weights["accomplice"]
        
    return score
