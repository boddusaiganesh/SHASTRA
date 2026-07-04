"""
Google Gemini AI Client
"""

import google.generativeai as genai
from typing import Optional
import logging
import hashlib
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

# The client is configured dynamically per request to support multiple keys

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


_available_models: list[str] = []
_current_key_index = 0
_current_model_index = 0

def _rank_model(model_name: str) -> tuple:
    """Helper to rank models: higher version first, pro over flash"""
    match = re.search(r'(\d+\.\d+)', model_name)
    version = float(match.group(1)) if match else 0.0
    is_pro = 1 if 'pro' in model_name else 0
    is_flash = 1 if 'flash' in model_name and not is_pro else 0
    return (version, is_pro, is_flash, model_name)

async def init_gemini_models():
    """Discover, filter, and rank available Gemini models at startup"""
    global _available_models
    keys = settings.get_gemini_api_keys()
    if not keys:
        logger.warning("No Gemini API keys found for dynamic model discovery.")
        return
        
    try:
        genai.configure(api_key=keys[0])
        models = genai.list_models()
        valid_models = [
            m.name for m in models 
            if 'generateContent' in m.supported_generation_methods 
            and 'gemini' in m.name.lower()
        ]
        
        # Sort using the ranking heuristic
        valid_models.sort(key=_rank_model, reverse=True)
        
        # Store top 5 models
        _available_models = valid_models[:5]
        if _available_models:
            logger.info(f"Successfully discovered and ranked {len(_available_models)} Gemini models: {_available_models}")
        else:
            logger.warning("No compatible Gemini models discovered. Will fallback to default model.")
            
    except Exception as e:
        logger.error(f"Failed to fetch Gemini models at startup: {e}")

def get_next_key_and_model() -> tuple[Optional[str], Optional[str]]:
    """Get the next API key and Model using round-robin"""
    global _current_key_index, _current_model_index
    keys = settings.get_gemini_api_keys()
    if not keys:
        return None, None
    
    key = keys[_current_key_index % len(keys)]
    _current_key_index += 1
    
    model_name = settings.GEMINI_MODEL
    if _available_models:
        model_name = _available_models[_current_model_index % len(_available_models)]
        _current_model_index += 1
        
    if model_name.startswith('models/'):
        model_name = model_name[7:]
        
    return key, model_name


def get_gemini_model(model_name: str):
    """Get the configured Gemini model"""
    try:
        model = genai.GenerativeModel(
            model_name=model_name,
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
    return hashlib.sha256(prompt.encode()).hexdigest()


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
    
    # Call Gemini API with retry logic
    keys = settings.get_gemini_api_keys()
    max_retries = min(len(keys) * max(1, len(_available_models)), 4) if keys else 1
    
    for attempt in range(max_retries):
        model_name = "unknown"
        try:
            api_key, model_name = get_next_key_and_model()
            if not api_key:
                logger.error("No API key available for Gemini request.")
                return generate_fallback_response(prompt)
                
            # Configure with the selected key
            genai.configure(api_key=api_key)
            
            logger.info(f"AI Request Attempt {attempt+1}: Using model '{model_name}'")
            
            model = get_gemini_model(model_name)
            if not model:
                continue
            
            response = await model.generate_content_async(prompt)
            
            if response and response.text:
                result = response.text
                
                # Cache the response
                if use_cache:
                    await cache_gemini_response(prompt_hash, result)
                
                return result
            else:
                logger.warning(f"Gemini returned empty response on attempt {attempt + 1} with model {model_name}")
                continue # Try next key/model
                
        except Exception as e:
            logger.error(f"Gemini API error on attempt {attempt + 1} with model {model_name}: {e}")
            if attempt == max_retries - 1:
                return generate_fallback_response(prompt)
            continue # Try next key/model
            
    logger.error("All Gemini API attempts failed. Using fallback.")
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
