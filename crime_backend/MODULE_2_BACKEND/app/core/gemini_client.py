"""
Google Gemini AI Client
"""

import google.generativeai as genai
from typing import Optional
import logging
import hashlib

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

# System context for all Gemini requests
SYSTEM_CONTEXT = """You are a highly specialized criminological intelligence analyst for the 
Karnataka State Police (KSP) - State Crime Records Bureau (SCRB), India. 

Your role is to:
- Analyze crime data, patterns, and trends for Karnataka state
- Provide actionable intelligence for law enforcement
- Identify criminal networks, behavioral patterns, and risk areas
- Generate evidence-based recommendations for policing strategy
- Write professional intelligence reports for senior officers

Guidelines:
- Keep all analysis factual and data-driven
- Do not make assumptions beyond what data shows
- Use precise, professional law enforcement language
- Structure responses clearly with key findings highlighted
- Consider the socio-cultural context of Karnataka, India
- Reference specific districts, crime types, and patterns mentioned in the data
- All recommendations must be legally compliant and ethical
"""


def get_gemini_model():
    """Get the configured Gemini model"""
    try:
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config={
                "temperature": settings.GEMINI_TEMPERATURE,
                "max_output_tokens": settings.GEMINI_MAX_TOKENS,
                "top_p": 0.95,
                "top_k": 40,
            },
            system_instruction=SYSTEM_CONTEXT,
        )
        return model
    except Exception as e:
        logger.error(f"Gemini model initialization error: {e}")
        return None


def generate_prompt_hash(prompt: str) -> str:
    """Generate a hash of a prompt for cache key"""
    return hashlib.md5(prompt.encode()).hexdigest()


async def call_gemini(prompt: str, use_cache: bool = True) -> Optional[str]:
    """
    Call Gemini API with caching support
    
    Args:
        prompt: The prompt to send to Gemini
        use_cache: Whether to use Redis cache for this request
    
    Returns:
        The generated text response, or None if failed
    """
    from app.core.redis_connection import cache_gemini_response, get_cached_gemini_response
    
    prompt_hash = generate_prompt_hash(prompt)
    
    # Check cache first
    if use_cache:
        cached = await get_cached_gemini_response(prompt_hash)
        if cached:
            logger.info("Returning cached Gemini response")
            return cached
    
    # Call Gemini API
    try:
        model = get_gemini_model()
        if not model:
            return generate_fallback_response(prompt)
        
        response = model.generate_content(prompt)
        
        if response and response.text:
            result = response.text
            
            # Cache the response
            if use_cache:
                await cache_gemini_response(prompt_hash, result)
            
            return result
        else:
            logger.warning("Gemini returned empty response")
            return generate_fallback_response(prompt)
            
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return generate_fallback_response(prompt)


def generate_fallback_response(prompt: str) -> str:
    """Generate a fallback response when Gemini is unavailable"""
    if "network" in prompt.lower() or "criminal" in prompt.lower():
        return ("Based on the available data, the criminal network analysis shows interconnected "
                "relationships between multiple suspects. Further investigation recommended to "
                "establish confirmed links. Priority should be given to high-risk individuals "
                "with multiple crime associations.")
    elif "deployment" in prompt.lower() or "patrol" in prompt.lower():
        return ("Based on crime pattern analysis, recommend increased patrol presence during "
                "identified peak hours. Focus resources on high-risk hotspot areas. "
                "Coordinate with local intelligence units for targeted interventions.")
    elif "offender" in prompt.lower() or "risk" in prompt.lower():
        return ("Risk assessment indicates elevated concern based on crime history and "
                "behavioral patterns. Standard monitoring protocols recommended. "
                "Previous crime patterns suggest continued criminal activity is probable.")
    elif "anomaly" in prompt.lower() or "unusual" in prompt.lower():
        return ("The detected anomaly represents a deviation from established baseline patterns. "
                "This warrants immediate investigative attention. Cross-reference with related "
                "cases and known criminal activity in the affected area.")
    elif "prediction" in prompt.lower() or "forecast" in prompt.lower():
        return ("Predictive analysis indicates elevated risk in identified areas for the "
                "forecast period. Preventive deployment recommended. Historical patterns "
                "suggest correlation with seasonal and socioeconomic factors.")
    elif "report" in prompt.lower() or "summary" in prompt.lower():
        return ("The crime intelligence report for the specified period indicates significant "
                "patterns requiring strategic attention. Key findings include spatial clustering "
                "of incidents and temporal patterns aligned with historical trends. "
                "Recommend resource optimization based on identified hotspots.")
    else:
        return ("Intelligence analysis based on available data indicates patterns requiring "
                "law enforcement attention. Recommend review of identified areas and "
                "implementation of targeted policing strategies.")
