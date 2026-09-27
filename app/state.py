from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AlertState:
    path: str
    active: bool = False
    triggered_at: Optional[datetime] = None
    last_percent: float = 0.0
    next_reminder_at: Optional[datetime] = None
