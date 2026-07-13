from pydantic import BaseModel
from typing import Optional, List
from datetime import date

class UpdateOffenderRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    aliases: Optional[List[str]] = None
    contact_number: Optional[str] = None
    address: Optional[str] = None
    occupation: Optional[str] = None
    status: Optional[str] = None
    gang_affiliation: Optional[str] = None
    modus_operandi_summary: Optional[str] = None
    known_associates: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    typical_targets: Optional[str] = None
