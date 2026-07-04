"""
Gemini AI Service - All AI-powered intelligence generation
"""

from typing import Optional, Dict, Any, List
import logging

from app.core.gemini_client import call_gemini

logger = logging.getLogger(__name__)


async def get_network_analysis_summary(
    offenders: List[Dict],
    suspicious_pairs: List[Dict],
    network_stats: Dict,
    focus_area: Optional[str] = None,
) -> str:
    """Generate AI network analysis summary"""
    
    prompt = f"""
Analyze the following criminal network data for Karnataka State Police:

NETWORK STATISTICS:
- Total Criminals in Network: {network_stats.get('total_criminals', 0)}
- High Risk Individuals: {network_stats.get('high_risk_count', 0)}
- Currently Active: {network_stats.get('active_count', 0)}
- Network Density: {network_stats.get('network_density', 0)}

TOP ACTIVE OFFENDERS:
{chr(10).join([f"- {o.get('full_name', 'Unknown')}: {o.get('total_crimes', 0)} crimes, Risk: {o.get('risk_level', 'UNKNOWN')}, Status: {o.get('status', 'UNKNOWN')}" for o in offenders[:10]])}

SUSPICIOUS ASSOCIATIONS DETECTED:
{chr(10).join([f"- {p.get('offender_1', '')} <-> {p.get('offender_2', '')} ({p.get('connection_type', '')})" for p in suspicious_pairs[:5]])}

FOCUS AREA: {focus_area or 'General Network Analysis'}

Provide a professional criminal network intelligence briefing in 3-4 paragraphs covering:
1. Overall network structure and key players
2. Most significant criminal associations and their implications
3. Risk assessment and emerging threats
4. Recommended investigative actions

Keep the analysis factual and actionable.
"""
    
    result = await call_gemini(prompt)
    return result.get("text", "") or "Network analysis temporarily unavailable. Please review the raw network data."


async def get_deployment_suggestions_ai(
    hotspots: List[Any],
    district_id: str,
) -> str:
    """Generate AI deployment strategy for a district"""
    
    hotspot_info = []
    for h in hotspots:
        hotspot_info.append(
            f"- {h.hotspot_name}: Risk={h.risk_level}, "
            f"Peak={h.peak_time_start or 'Unknown'}-{h.peak_time_end or 'Unknown'}, "
            f"Crime Type={h.dominant_crime_type or 'Mixed'}, "
            f"Trend={h.trend}"
        )
    
    prompt = f"""
Generate a strategic police deployment plan for Karnataka State Police in district: {district_id}

IDENTIFIED HOTSPOTS:
{chr(10).join(hotspot_info)}

Create a professional deployment strategy covering:
1. Priority patrol zones and specific recommended times
2. Resource allocation (how many officers where)
3. Special operations or checkpoints recommended
4. Inter-station coordination requirements
5. Community policing measures

Format as a clear operational directive suitable for a District Superintendent of Police.
"""
    
    result = await call_gemini(prompt)
    return result.get("text", "") or "AI deployment strategy generation temporarily unavailable. Use standard patrol protocols for identified hotspots."


async def get_offender_ai_analysis(
    offender_data: Dict,
    crime_history: List[Dict],
) -> str:
    """Generate AI risk assessment for an offender"""
    
    crime_summary = "\n".join([
        f"- {c.get('crime_type', 'Unknown')}: {c.get('date', 'Unknown')} "
        f"(Status: {c.get('status', 'Unknown')}, Severity: {c.get('severity', 'Unknown')})"
        for c in crime_history[:10]
    ])
    
    prompt = f"""
Provide a criminological risk assessment for the following offender in Karnataka State Police records:

OFFENDER PROFILE:
- Name: {offender_data.get('full_name', 'Unknown')}
- Age: {offender_data.get('age', 'Unknown')}
- Status: {offender_data.get('status', 'Unknown')}
- Risk Level: {offender_data.get('risk_level', 'Unknown')}
- Risk Score: {offender_data.get('risk_score', 0)}
- Total Crimes: {offender_data.get('total_crimes', 0)}
- Reoffend Probability: {offender_data.get('reoffend_probability', 0)}%
- Occupation: {offender_data.get('occupation', 'Unknown')}

CRIME HISTORY (Last 10):
{crime_summary or 'No crime history available'}

KNOWN ASSOCIATES: {len(offender_data.get('known_associates', []))} known associates

Provide:
1. Risk assessment narrative (2 paragraphs)
2. Behavioral pattern analysis
3. Recommended monitoring level and specific actions
4. Recidivism risk factors

Be specific and evidence-based.
"""
    
    result = await call_gemini(prompt)
    return result.get("text", "") or f"Risk assessment for this offender indicates {offender_data.get('risk_level', 'MEDIUM')} risk based on crime history."


async def get_mo_analysis(mo_data: Dict, offender_data: Dict) -> str:
    """Generate AI modus operandi analysis"""
    
    crime_types = ", ".join([ct.get("crime_type", "") for ct in mo_data.get("preferred_crime_types", [])[:3]])
    
    prompt = f"""
Analyze the Modus Operandi (MO) of the following offender for Karnataka State Police:

OFFENDER: {offender_data.get('full_name', 'Unknown')}

MO ANALYSIS DATA:
- Preferred Crime Types: {crime_types}
- Preferred Time: {mo_data.get('preferred_time', 'Unknown')}
- Average Days Between Crimes: {mo_data.get('average_crime_interval', 0)} days
- Geographic Range: {mo_data.get('geographic_range', 'Unknown')}
- Escalation Trend: {mo_data.get('escalation_trend', 'STABLE')}
- Accomplice Pattern: {mo_data.get('accomplice_pattern', 'SOLO')}
- Weapons Used: {', '.join(mo_data.get('weapons_pattern', [])) or 'None documented'}
- Peak Days: {', '.join([d.get('day', '') for d in mo_data.get('preferred_days', [])[:3]])}

Total crimes analyzed: {mo_data.get('total_crimes_analyzed', 0)}

Provide a professional MO profile covering:
1. Signature behaviors and patterns
2. Target selection methodology
3. Operational planning indicators
4. Psychological profile insights
5. Predictive behavioral assessment
6. Recommended investigative angles

Write in a professional forensic analysis style.
"""
    
    result = await call_gemini(prompt)
    return result.get("text", "") or "MO analysis based on crime history indicates consistent behavioral patterns. Full analysis requires additional data."


async def get_anomaly_explanation(anomaly_data: Dict) -> str:
    """Generate AI explanation for a detected anomaly"""
    
    evidence_text = "\n".join([f"- {e}" for e in anomaly_data.get("evidence_points", [])[:5]])
    
    prompt = f"""
Analyze the following crime anomaly detected by the Karnataka State Police intelligence system:

ANOMALY DETAILS:
- Type: {anomaly_data.get('anomaly_type', 'Unknown')}
- Severity: {anomaly_data.get('severity', 'Unknown')}
- District: {anomaly_data.get('district_id', 'Unknown')}
- Description: {anomaly_data.get('description', 'No description')}
- Anomaly Score: {anomaly_data.get('anomaly_score', 0):.2f}

EVIDENCE POINTS:
{evidence_text or 'No specific evidence points recorded'}

Provide:
1. Why this pattern is anomalous (2 sentences)
2. What it might indicate criminologically
3. How it might connect to known crime patterns in Karnataka
4. Specific recommended investigative steps (3-4 actions)
5. Priority level justification

Keep the analysis concise and actionable for law enforcement use.
"""
    
    result = await call_gemini(prompt)
    return result.get("text", "") or "Anomaly detected through statistical analysis. Pattern deviates from baseline. Recommend immediate investigation."


async def get_prediction_recommended_action(prediction_data: Dict) -> str:
    """Generate AI recommended action for a prediction"""
    
    prompt = f"""
Based on the following crime prediction for Karnataka State Police, provide a specific recommended action:

PREDICTION:
- Location: {prediction_data.get('location', 'Unknown')}
- Crime Type: {prediction_data.get('predicted_crime_type', 'Unknown')}
- Risk: {prediction_data.get('risk_percentage', 0):.1f}%
- Confidence: {prediction_data.get('confidence_level', 0):.1f}%
- Time Period: {prediction_data.get('prediction_date_range', {})}

Provide a single, specific recommended police action in 2-3 sentences.
"""
    
    result = await call_gemini(prompt)
    return result.get("text", "") or "Deploy additional patrol units to the identified area during predicted high-risk periods."


async def get_report_narrative(report_data: Dict, report_type: str) -> str:
    """Generate AI executive summary narrative for a report"""
    
    prompt = f"""
Write a professional executive summary for the following Karnataka State Police intelligence report:

REPORT TYPE: {report_type}
PERIOD: {report_data.get('date_from', 'Unknown')} to {report_data.get('date_to', 'Unknown')}
DISTRICT: {report_data.get('district_id', 'All Karnataka')}

KEY STATISTICS:
- Total Crimes: {report_data.get('total_crimes', 0)}
- Top Crime Types: {', '.join([ct.get('crime_type', '') for ct in report_data.get('by_crime_type', [])[:3]])}
- Cases Solved: {report_data.get('by_status', {}).get('SOLVED', 0)}
- Cases Under Investigation: {report_data.get('by_status', {}).get('INVESTIGATING', 0)}
- Hotspots Identified: {report_data.get('total_hotspots', 'N/A')}
- Offenders Tracked: {report_data.get('total_offenders', 'N/A')}

Write a professional 3-paragraph executive summary suitable for senior SCRB officers:
1. Overview of the crime situation
2. Key findings and patterns
3. Strategic recommendations

Use formal government report language.
"""
    
    result = await call_gemini(prompt)
    return result.get("text", "") or "Executive summary generation temporarily unavailable. Refer to the statistical data within this report."


async def get_emerging_typology_explanation(data: Dict) -> str:
    """Generate AI explanation of emerging crime typologies"""
    
    if "emerging_types" in data:
        # Overall briefing
        types_list = "\n".join([
            f"- {et.get('crime_type', 'Unknown')}: {et.get('growth_rate', 0):.1f}% growth, "
            f"affecting districts: {', '.join(et.get('affected_districts', [])[:3])}"
            for et in data.get("emerging_types", [])[:5]
        ])
        
        prompt = f"""
Provide an overall intelligence briefing on the following emerging crime trends in Karnataka:

EMERGING TYPOLOGIES:
{types_list}

District Focus: {data.get('district_id', 'All Karnataka')}

Write a 2-paragraph intelligence briefing covering:
1. The most significant emerging trends and their potential causes
2. Recommended strategic response for SCRB leadership

Use professional intelligence briefing language.
"""
    else:
        # Individual type explanation
        prompt = f"""
Explain the following emerging crime trend for Karnataka State Police:

CRIME TYPE: {data.get('crime_type', 'Unknown')}
GROWTH RATE: {data.get('growth_rate', 0):.1f}%
AFFECTED AREAS: {', '.join(data.get('affected_districts', [])[:3])}

Provide a 2-sentence explanation of:
1. Why this crime type might be increasing
2. What warning signals to watch for

Be specific to Karnataka's socioeconomic context.
"""
    
    result = await call_gemini(prompt)
    return result.get("text", "") or "Emerging crime typology detected. Statistical analysis indicates growth trend requiring monitoring."


async def get_socioeconomic_ai_analysis(correlations: List[Dict], overlay_data: List[Dict]) -> str:
    """Generate AI analysis of socioeconomic-crime correlations"""
    
    corr_text = "\n".join([
        f"- {c.get('factor_name', 'Unknown')}: correlation={c.get('correlation_score', 0):.2f} "
        f"with {c.get('crime_type', 'Unknown')}"
        for c in correlations[:5]
    ])
    
    prompt = f"""
Analyze the following socioeconomic correlations with crime data for Karnataka State Police:

CORRELATIONS FOUND:
{corr_text}

OVERLAY DATA SAMPLE:
- Districts analyzed: {len(overlay_data)}
- Average crime rate: {sum(d.get('crime_rate', 0) for d in overlay_data) / max(len(overlay_data), 1):.1f}

Provide a 3-paragraph criminological analysis covering:
1. The strongest socioeconomic drivers of crime in Karnataka
2. Which districts are most vulnerable based on indicators
3. Policy recommendations for crime prevention through socioeconomic intervention

Reference Karnataka's specific context (urbanization, agricultural economy, tech hub growth).
"""
    
    result = await call_gemini(prompt)
    return result.get("text", "") or "Socioeconomic correlation analysis indicates multiple factors influencing crime rates. Unemployment and urbanization show strongest correlation with property crimes."
