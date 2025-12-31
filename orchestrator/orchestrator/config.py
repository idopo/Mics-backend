import json
from pathlib import Path
from typing import Any, Dict


class Config:
    def __init__(self, path: str):
        self.path = Path(path)
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self):
        if not self.path.exists():
            raise RuntimeError(f"Config file not found: {self.path}")

        with self.path.open("r") as f:
            self._data = json.load(f)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def require(self, key: str):
        if key not in self._data:
            raise RuntimeError(f"Missing required config key: {key}")
        return self._data[key]
