#!/usr/bin/env python3
"""AKIS G7 — Knowledge refresh for a0-evol project.

Scans the project directory and updates project_knowledge.json
with current file structure, recent changes, gotchas, and hot cache.

Usage:
  python .github/scripts/knowledge.py              # full scan + update
  python .github/scripts/knowledge.py --update     # same
  python .github/scripts/knowledge.py --report     # print report only
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

IGNORED = {'.git', '__pycache__', '.a0proj', '.venv', 'venv', '.github', 'node_modules'}


def scan_files(root: Path) -> Dict[str, str]:
    """Scan all tracked files and return {rel_path: sha256_hash}."""
    files = {}
    for path in root.rglob('*'):
        if path.is_file():
            rel = path.relative_to(root)
            parts = rel.parts
            if any(p in IGNORED for p in parts):
                continue
            try:
                content = path.read_bytes()
                files[str(rel)] = hashlib.sha256(content).hexdigest()
            except OSError:
                files[str(rel)] = 'UNREADABLE'
    return files


def load_previous_knowledge() -> Dict:
    """Load previous knowledge base if it exists."""
    knowledge_path = PROJECT_ROOT / 'project_knowledge.json'
    if knowledge_path.exists():
        try:
            return json.loads(knowledge_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def detect_changes(prev: Dict, curr_files: Dict) -> List[str]:
    """Detect what changed since last scan."""
    prev_files = prev.get('file_hashes', {})
    changes = []
    
    for path, h in curr_files.items():
        if path not in prev_files:
            changes.append(f"ADDED {path}")
        elif prev_files[path] != h:
            changes.append(f"MODIFIED {path}")
    
    for path in prev_files:
        if path not in curr_files:
            changes.append(f"REMOVED {path}")
    
    return changes


def extract_gotchas(root: Path) -> List[str]:
    """Extract gotchas from code comments and known patterns."""
    gotchas = []
    
    # Check engine.py for known issues
    engine_path = root / 'helpers' / 'engine.py'
    if engine_path.exists():
        content = engine_path.read_text()
        if 'except ImportError' in content:
            gotchas.append("engine.py has dual import paths (try/except ImportError) — standalone tests need correct sys.path setup")
    
    # Check registry.py
    registry_path = root / 'helpers' / 'registry.py'
    if registry_path.exists():
        content = registry_path.read_text()
        if 'if expressed is None' in content:
            gotchas.append("registry.py memorize() has None guards for expressed/explored — must test with real LLM calls")
    
    # Check for per_agent_config
    plugin_path = root / 'plugin.yaml'
    if plugin_path.exists():
        content = plugin_path.read_text()
        if 'per_agent_config: true' in content:
            gotchas.append("Plugin uses per_agent_config=true — settings are scoped per agent profile, not global")
    
    return gotchas


def build_knowledge() -> Dict:
    """Build complete knowledge base."""
    prev = load_previous_knowledge()
    curr_files = scan_files(PROJECT_ROOT)
    changes = detect_changes(prev, curr_files)
    gotchas = extract_gotchas(PROJECT_ROOT)
    
    # Hot cache: most recently modified files (top 10)
    mtimes = []
    for p in PROJECT_ROOT.rglob('*'):
        if p.is_file():
            rel = p.relative_to(PROJECT_ROOT)
            parts = rel.parts
            if any(part in IGNORED for part in parts):
                continue
            try:
                mtimes.append((str(rel), p.stat().st_mtime))
            except OSError:
                pass
    mtimes.sort(key=lambda x: x[1], reverse=True)
    hot_cache = [{"path": p, "mtime": datetime.fromtimestamp(t, tz=timezone.utc).isoformat()}
                 for p, t in mtimes[:10]]
    
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(curr_files),
        "file_hashes": curr_files,
        "recent_changes": changes[-20:],  # Last 20 changes
        "gotchas": gotchas,
        "hot_cache": hot_cache,
        "project_path": str(PROJECT_ROOT),
    }


def main():
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        return
    
    knowledge = build_knowledge()
    
    if '--report' in sys.argv:
        print(json.dumps(knowledge, indent=2))
        return
    
    output_path = PROJECT_ROOT / 'project_knowledge.json'
    output_path.write_text(json.dumps(knowledge, indent=2) + '\n')
    print(f"Knowledge base updated: {output_path}")
    print(f"  Files: {knowledge['file_count']}")
    print(f"  Recent changes: {len(knowledge['recent_changes'])}")
    print(f"  Gotchas: {len(knowledge['gotchas'])}")


if __name__ == '__main__':
    main()
