from dataclasses import dataclass, field
from typing import Any
@dataclass
class WorkerContext:
    request: str
    outputs: dict[str,Any]=field(default_factory=dict)
