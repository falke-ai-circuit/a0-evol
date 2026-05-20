"""
EVOL Stores — Append-Only JSONL Persistence.

StateStore: organism vitals, heartbeat snapshots.
MaterialStore: accumulated absorb events.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class StateStore:
    """Append-only store for organism state snapshots (heartbeat vitals)."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, data: Dict[str, Any]):
        with open(self.path, "a") as f:
            f.write(json.dumps(data) + "\n")

    def tail(self, n: int = 20) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text().splitlines()
        entries = []
        for line in lines[-n:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return entries

    def all(self) -> List[Dict[str, Any]]:
        return self.tail(99999)

    def clear(self):
        if self.path.exists():
            self.path.unlink()


class MaterialStore:
    """Append-only store for absorbed material events."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, data: Dict[str, Any]):
        with open(self.path, "a") as f:
            f.write(json.dumps(data) + "\n")

    def tail(self, n: int = 50) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text().splitlines()
        entries = []
        for line in lines[-n:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return entries

    def all(self) -> List[Dict[str, Any]]:
        return self.tail(99999)

    def clear(self):
        if self.path.exists():
            self.path.unlink()
