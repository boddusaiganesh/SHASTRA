"""
Risk Scoring - Random Forest Classifier for district and location risk assessment
"""

import numpy as np
from typing import List, Dict, Any
import logging
import os
import joblib
from datetime import date

logger = logging.getLogger(__name__)


def calculate_offender_recidivism_risk(offender: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate recidivism risk score and factors for an individual offender
    """
    factors = []
    base_prob = 30.0  # Base probability of reoffending

    # Total crimes weight (up to 30%)
    total_crimes = offender.get("total_crimes", 0) or 0
    if total_crimes > 5:
        base_prob += 30.0
        factors.append(f"High frequency of offenses ({total_crimes} crimes)")
    elif total_crimes > 2:
        base_prob += 15.0
        factors.append(f"Multiple recorded offenses ({total_crimes} crimes)")
    elif total_crimes == 2:
        base_prob += 5.0
        factors.append("Second-time offender")

    # Known associates weight (up to 15%)
    associates = offender.get("known_associates", []) or []
    num_associates = len(associates)
    if num_associates > 3:
        base_prob += 15.0
        factors.append(f"Large criminal network ({num_associates} known associates)")
    elif num_associates > 0:
        base_prob += 5.0
        factors.append("Has known criminal associates")

    # Last offense recency (up to 15%)
    last_offense = offender.get("last_offense_date")
    if last_offense:
        try:
            if isinstance(last_offense, str):
                last_offense_date = date.fromisoformat(last_offense)
            else:
                last_offense_date = last_offense
            days_since = (date.today() - last_offense_date).days
            if days_since < 180:
                base_prob += 15.0
                factors.append("Recent offense within the last 6 months")
            elif days_since < 365:
                base_prob += 10.0
                factors.append("Offense within the past year")
            elif days_since > 1095:  # 3+ years
                base_prob -= 10.0
        except Exception:
            pass

    # Status weight
    status = offender.get("status", "ACTIVE")
    if status == "ACTIVE":
        base_prob += 10.0
    elif status == "IMPRISONED" or status == "PRISON":
        base_prob -= 15.0
        factors.append("Currently imprisoned")

    probability = max(5.0, min(base_prob, 95.0))
    if probability >= 70.0:
        risk_level = "HIGH"
    elif probability >= 40.0:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    if not factors:
        factors.append("No significant risk factors identified")

    return {
        "probability": round(probability, 1),
        "risk_level": risk_level,
        "factors": factors
    }


def calculate_district_risk(
    features: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculate risk score for a district using Random Forest model or rule-based fallback
    """
    model_path = "app/ml_models/saved_models/risk_scoring_rf.pkl"
    encoder_path = "app/ml_models/saved_models/risk_label_encoder.pkl"
    
    use_ml = False
    risk_score = 50.0
    risk_level = "MEDIUM"
    
    if os.path.exists(model_path) and os.path.exists(encoder_path):
        try:
            model = joblib.load(model_path)
            le = joblib.load(encoder_path)
            
            feature_cols = [
                "historical_crime_rate", "unemployment_rate", "poverty_index",
                "population_density", "hotspot_count", "urbanization_rate",
                "young_male_population", "cctv_coverage", "street_lighting_coverage",
            ]
            X = np.array([[features.get(col, 0.0) for col in feature_cols]])
            y_pred = model.predict(X)
            risk_level = le.inverse_transform(y_pred)[0]
            
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(X)[0]
                class_scores = []
                for cls_name in le.classes_:
                    if cls_name == "HIGH":
                        class_scores.append(85.0)
                    elif cls_name == "MEDIUM":
                        class_scores.append(55.0)
                    else:
                        class_scores.append(20.0)
                risk_score = float(sum(p * s for p, s in zip(probs, class_scores)))
            else:
                risk_score = 85.0 if risk_level == "HIGH" else (55.0 if risk_level == "MEDIUM" else 20.0)
            use_ml = True
        except Exception as e:
            logger.warning(f"ML risk prediction failed: {e}. Falling back to rules.")
            
    if not use_ml:
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
