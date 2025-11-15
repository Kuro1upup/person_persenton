from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from pydantic import BaseModel

from models.sql.slide import SlideModel


class PresentationWithSlides(BaseModel):
    id: uuid.UUID
    content: str
    n_slides: int
    language: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tone: Optional[str] = None
    verbosity: Optional[str] = None
    slides: List[SlideModel]
    reference_markers: Optional[List[Dict[str, Any]]] = None
    webSearchResources: Optional[Dict[str, Any]] = None
