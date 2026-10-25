from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentVersionBase(BaseModel):
    version: int
    content_snapshot: str


class DocumentVersionRead(DocumentVersionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    created_by: int
    created_at: datetime


class DocumentVersionReadWithCreator(DocumentVersionRead):
    creator_email: Optional[str] = None
