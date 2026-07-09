from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionContext:
    product_id: str
    product_path: Path
    permission_level: int = 2
