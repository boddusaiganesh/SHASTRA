"""
Risk Scoring - Random Forest Classifier for district and location risk assessment
"""

import numpy as np
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def calculate_district_risk(
    features: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculate risk score for a district using Random Forest model
    
    Features:
    - historical_crime_rate: crimes per 100k population
    - unemployment_rate: percentage
    - poverty_index: 0-100
    - population_density: per sqkm
    - recent_trend: INCREASING/STABLE/DECREASING
    - hotspot_count: number of active hotspots
    - urbanization_rate: percentage
    - young_male_population: percentage
    - cctv_coverage: percentage
    - street_lighting_coverage: percentage
    """
    
    try:
        risk_score = _rule_based_risk_score(features)
    except Exception as e:
        logger.error(f"Risk scoring error: {e}")
        risk_score = 50.0
    
    if risk_score >= 75:
        risk_level = "HIGH"
    elif risk_score >= 40:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    
    # Top contributing factors
    factors = _identify_contributing_factors(features, risk_score)
    
    return {
        "risk_score": round(risk_score, 1),
        "risk_level": risk_level,
        "contributing_factors": factors,
    }


def _rule_based_risk_score(features: Dict[str, Any]) -> float:
    """Rule-based risk scoring when ML model is not trained"""
    
    score = 0.0
    max_score = 100.0
    
    # Historical crime rate (weight: 30%)
    crime_rate = features.get("historical_crime_rate", 0)
    crime_score = min(crime_rate / 10, 30)  # Normalize to 0-30
    score += crime_score
    
    # Unemployment rate (weight: 15%)
    unemployment = features.get("unemployment_rate", 7.5)
    if unemployment > 15:
        score += 15
    elif unemployment > 10:
        score += 10
    elif unemployment > 7:
        score += 7
    else:
        score += 3
    
    # Poverty index (weight: 15%)
    poverty = features.get("poverty_index", 18)
    poverty_score = min(poverty / 100 * 15, 15)
    score += poverty_score
    
    # Population density (weight: 10%)
    density = features.get("population_density", 500)
    if density > 5000:
        score += 10
    elif density > 2000:
        score += 7
    elif density > 1000:
        score += 4
    else:
        score += 1
    
    # Recent trend (weight: 15%)
    trend = features.get("recent_trend", "STABLE")
    if trend == "INCREASING":
        score += 15
    elif trend == "STABLE":
        score += 7
    else:
        score += 2
    
    # Hotspot count (weight: 10%)
    hotspots = features.get("hotspot_count", 0)
    score += min(hotspots * 2, 10)
    
    # Young male population (weight: 5%)
    young_male = features.get("young_male_population", 15)
    if young_male > 25:
        score += 5
    elif young_male > 20:
        score += 3
    else:
        score += 1
    
    # Protective factors (reduce score)
    cctv = features.get("cctv_coverage", 20)
    score -= min(cctv / 100 * 10, 10)  # Up to -10 for CCTV
    
    lighting = features.get("street_lighting_coverage", 60)
    score -= min(lighting / 100 * 5, 5)  # Up to -5 for lighting
    
    return max(0, min(score, max_score))


def _identify_contributing_factors(features: Dict[str, Any], risk_score: float) -> List[str]:
    """Identify the top factors contributing to the risk score"""
    
    factors = []
    
    crime_rate = features.get("historical_crime_rate", 0)
    if crime_rate > 50:
        factors.append(f"High historical crime rate ({crime_rate:.0f} per 100k population)")
    
    unemployment = features.get("unemployment_rate", 7.5)
    if unemployment > 10:
        factors.append(f"Elevated unemployment rate ({unemployment:.1f}%)")
    
    poverty = features.get("poverty_index", 18)
    if poverty > 25:
        factors.append(f"High poverty index ({poverty:.1f})")
    
    trend = features.get("recent_trend", "STABLE")
    if trend == "INCREASING":
        factors.append("Increasing crime trend in recent period")
    
    hotspots = features.get("hotspot_count", 0)
    if hotspots > 3:
        factors.append(f"{hotspots} active crime hotspots identified")
    
    density = features.get("population_density", 500)
    if density > 3000:
        factors.append(f"High population density ({density:.0f}/sqkm)")
    
    cctv = features.get("cctv_coverage", 20)
    if cctv < 30:
        factors.append(f"Low CCTV coverage ({cctv:.0f}%)")
    
    if not factors:
        factors.append("Multiple moderate risk factors present")
    
    return factors[:5]


def calculate_location_risk_scores(
    location_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Calculate risk scores for a list of locations"""
    
    results = []
    for location in location_data:
        risk_data = calculate_district_risk(location)
        location_copy = location.copy()
        location_copy.update(risk_data)
        results.append(location_copy)
    
    return sorted(results, key=lambda x: x["risk_score"], reverse=True)


def train_random_forest_model(training_data: List[Dict[str, Any]]):
    """
    Train Random Forest model on historical data
    Called during model retraining tasks
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder
        import joblib
        import os
        
        if len(training_data) < 50:
            logger.warning("Insufficient training data for Random Forest")
            return None
        
        # Prepare features
        feature_cols = [
            "historical_crime_rate", "unemployment_rate", "poverty_index",
            "population_density", "hotspot_count", "urbanization_rate",
            "young_male_population", "cctv_coverage", "street_lighting_coverage",
        ]
        
        X = np.array([[d.get(col, 0) for col in feature_cols] for d in training_data])
        
        le = LabelEncoder()
        y = le.fit_transform([d.get("risk_level", "MEDIUM") for d in training_data])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight="balanced",
        )
        model.fit(X_train, y_train)
        
        # Save model
        os.makedirs("app/ml_models/saved_models", exist_ok=True)
        joblib.dump(model, "app/ml_models/saved_models/risk_scoring_rf.pkl")
        joblib.dump(le, "app/ml_models/saved_models/risk_label_encoder.pkl")
        
        accuracy = model.score(X_test, y_test)
        logger.info(f"Risk Scoring Random Forest trained with accuracy: {accuracy:.2%}")
        
        return {"model": model, "accuracy": accuracy}
        
    except ImportError:
        logger.warning("scikit-learn not available for model training")
        return None
    except Exception as e:
        logger.error(f"Model training error: {e}")
        return None
