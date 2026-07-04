from fastapi import APIRouter, Depends, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.gemini_client import call_gemini

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.post("/ask")
@limiter.limit("5/minute")
async def ask_assistant(
    request: Request,
    question: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # In a full implementation, you would fetch real-time summary data here
    # to ground the LLM in the current state of the database.
    # We use a mocked context representing the summary for now.
    context = "Karnataka state crime records indicate an overall decrease in property crimes but a slight uptick in cyber crimes in urban districts."
    
    prompt = f"""You are a crime-intelligence assistant for Karnataka State Police.
Use ONLY the following current statistics to answer. If the answer isn't in the data, say so.

DATA: {context}

QUESTION: {question}
"""
    result = await call_gemini(prompt)
    answer = result.get("text", "")
    is_fallback = result.get("is_fallback", False)
    
    if not answer:
        answer = "I'm currently unable to access the intelligence database. Please try again later."
        
    return {"success": True, "data": {"answer": answer, "is_fallback": is_fallback}}
