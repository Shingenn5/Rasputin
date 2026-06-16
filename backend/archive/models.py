from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

class ArchiveRetentionRule(BaseModel):
    id: str
    target_type: str  # e.g., 'mission', 'snapshot', 'export', 'artifact'
    duration_days: Optional[int]  # None for keep forever
    created_at: float

class ArchiveItem(BaseModel):
    id: str
    name: str
    type: str  # e.g., 'snapshot', 'mission', 'report', 'export', 'conversation', 'artifact', 'backup'
    source: str
    workspace: Optional[str]
    created_at: float
    archived_at: float
    size: int
    tags: List[str]
    retention_policy_id: Optional[str]
    metadata: Dict[str, Any]

class ArchiveSnapshot(ArchiveItem):
    pass

class ArchiveMission(ArchiveItem):
    pass

class ArchiveExport(ArchiveItem):
    pass

class ArchiveArtifact(ArchiveItem):
    pass

class ArchiveRestoreJob(BaseModel):
    id: str
    item_id: str
    status: str
    started_at: float
    completed_at: Optional[float]
    logs: List[str]
