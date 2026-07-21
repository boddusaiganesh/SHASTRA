import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

async def notify_high_priority_alert(alert: Dict[str, Any], recipients: List[str]):
    """
    Stub — wire to SMTP/SendGrid/Twilio when credentials are available.
    """
    logger.info(f"[NOTIFY] Would send alert '{alert.get('title')}' to {recipients}")
    if not recipients:
        return
        
    import smtplib
    from email.message import EmailMessage
    from app.core.config import settings
    
    msg = EmailMessage()
    msg["Subject"] = f"SHASTRA Alert: {alert.get('title')}"
    msg["From"] = getattr(settings, 'SMTP_FROM', 'noreply@shastra.gov.in')
    msg["To"] = ", ".join(recipients)
    msg.set_content(alert.get("description", ""))
    
    smtp_host = getattr(settings, 'SMTP_HOST', None)
    if not smtp_host:
        logger.warning(f"SMTP_HOST not set, skipping real email to {recipients}")
        return
        
    try:
        import asyncio
        
        def _send_email():
            with smtplib.SMTP(settings.SMTP_HOST, getattr(settings, 'SMTP_PORT', 587), timeout=10) as s:
                s.starttls()
                s.login(settings.SMTP_USER, settings.SMTP_PASS)
                s.send_message(msg)
                
        # Run the blocking SMTP call in a separate thread so it doesn't block the asyncio event loop
        await asyncio.wait_for(asyncio.to_thread(_send_email), timeout=15)
        logger.info(f"Alert email sent to {recipients}")
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
