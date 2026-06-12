from dataclasses import dataclass
import time
import json


@dataclass
class YeuxMouseEvent:
    version: int = 1
    device: str = "Lukintosh Yeux"
    type: str = "mouse"
    dx: int = 0
    dy: int = 0
    left: bool = False
    timestamp: float = 0.0

    def to_json(self) -> str:
        self.timestamp = time.time()
        return json.dumps({
            "version": self.version,
            "device": self.device,
            "type": self.type,
            "dx": self.dx,
            "dy": self.dy,
            "left": self.left,
            "timestamp": self.timestamp,
        })