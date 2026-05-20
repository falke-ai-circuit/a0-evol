"""
EVOL Knowledge — Three-Tier Memory System.

Tier 3: IDENTITY (agent.yaml, prompts/agent.system.main.specifics.md) — identity & behavioral level
Tier 2: KNOWLEDGE — wiki-style files with decay (profile/knowledge/)
Tier 1: CONTEXT — session-level memory

Movement rules:
  Knowledge entries gain weight through reinforcement
  Weight decays exponentially over time (decay_rate 0.95/day after 7-day grace)
  Phase-out at weight < 0.15
"""

import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ── Knowledge Tier (wiki-style files) ─────────────────────────────

DOMAIN_CLUSTERS = [
    "docker", "hostinger", "evol", "hermes", "model",
    "telegram", "memory", "network", "security", "coding",
    "infrastructure", "personality", "general",
]


def _knowledge_dir(profile_dir: str) -> Path:
    """Knowledge directory for a profile."""
    return Path(profile_dir) / "knowledge"


def classify_domain(text: str) -> str:
    """Classify text into a domain cluster."""
    text_lower = text.lower()
    keywords = {
        "docker": ["docker", "container", "compose", "image"],
        "hostinger": ["hostinger", "vps", "ip", "hetzner", "server"],
        "evol": ["evol", "cycle", "phase", "absorb", "reflect", "memorize"],
        "hermes": ["hermes", "gateway", "conductor", "orchestrator"],
        "model": ["model", "llm", "provider", "token", "inference"],
        "telegram": ["telegram", "bot", "message", "channel"],
        "memory": ["memory", "knowledge", "identity", "recall"],
        "network": ["network", "http", "api", "endpoint"],
        "security": ["security", "auth", "secret", "key", "token"],
        "coding": ["code", "python", "script", "function", "class"],
        "infrastructure": ["infrastructure", "deploy", "backup", "restore"],
        "personality": ["personality", "identity", "soul", "tone"],
    }
    best_domain = "general"
    best_score = 0
    for domain, kws in keywords.items():
        score = sum(1 for kw in kws if kw in text_lower)
        if score > best_score:
            best_score = score
            best_domain = domain
    return best_domain


def ensure_knowledge_entry(knowledge_dir: Path, title: str, content: str,
                           weight: float = 0.5, tags: Optional[List[str]] = None):
    """Write a knowledge entry to the appropriate domain directory."""
    domain = classify_domain(content)
    domain_dir = knowledge_dir / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    # Slugify title for filename
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().strip()).strip("-") or "entry"
    filepath = domain_dir / f"{slug}.md"

    # Build entry with YAML-like frontmatter
    entry = f"""---
title: "{title}"
date: {datetime.now().strftime('%Y-%m-%d')}
weight: {weight:.2f}
tags: {json.dumps(tags or [])}
---

# {title}

{content}

"""
    # If file exists, append with updated weight
    if filepath.exists():
        existing = filepath.read_text()
        # Update weight in frontmatter
        existing = re.sub(r"weight: [\d.]+", f"weight: {weight:.2f}", existing)
        filepath.write_text(existing)
    else:
        filepath.write_text(entry)

    return str(filepath)


# ── Decay System ───────────────────────────────────────────────────

def apply_decay_to_knowledge(knowledge_dir: Path, decay_rate: float = 0.95,
                            grace_days: int = 7) -> List[Dict[str, Any]]:
    """
    Apply exponential decay to all knowledge entries.
    decay_rate: multiplier per day (0.95 = lose 5% per day)
    grace_days: days before decay starts

    Returns list of entries that were phased out.
    """
    phased_out = []
    now = time.time()

    for domain_dir in knowledge_dir.iterdir():
        if not domain_dir.is_dir():
            continue
        for md_file in domain_dir.glob("*.md"):
            try:
                content = md_file.read_text()
                # Extract current weight and date
                weight_match = re.search(r"weight: ([\d.]+)", content)
                date_match = re.search(r"date: (\d{4}-\d{2}-\d{2})", content)
                if not weight_match:
                    continue

                current_weight = float(weight_match.group(1))

                # Calculate days since entry
                if date_match:
                    try:
                        entry_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                        days_old = (now - entry_date.timestamp()) / 86400
                    except ValueError:
                        days_old = 30  # conservative default
                else:
                    days_old = 30

                if days_old <= grace_days:
                    continue

                # Apply decay: weight *= decay_rate^(days - grace)
                decay_days = days_old - grace_days
                new_weight = current_weight * (decay_rate ** decay_days)

                if new_weight < 0.15:
                    md_file.unlink()
                    phased_out.append({"title": md_file.stem, "weight": current_weight,
                                       "new_weight": new_weight, "days_old": days_old})
                else:
                    # Update weight in file
                    new_content = re.sub(r"weight: [\d.]+", f"weight: {new_weight:.2f}", content)
                    md_file.write_text(new_content)

            except (OSError, re.error):
                pass

    return phased_out


# ── Knowledge Capacity Management ────────────────────────────────────

KNOWLEDGE_CAP_CHARS = 8000


def manage_knowledge_capacity(index_path: Path, new_entry: str) -> bool:
    """
    Add entry to knowledge index with capacity management.
    If file exceeds KNOWLEDGE_CAP_CHARS, trim lowest-weight entries.

    Returns True if entry was written.
    """
    if not index_path.exists():
        return False

    try:
        current = index_path.read_text()
    except OSError:
        return False

    if len(current) + len(new_entry) <= KNOWLEDGE_CAP_CHARS:
        # Append directly
        try:
            with open(index_path, "a") as f:
                f.write(new_entry + "\n")
            return True
        except OSError:
            return False

    # Need to trim: find sections with weight annotations
    sections = re.split(r"\n(?=## |### |§ )", current)

    if len(sections) <= 1:
        # Can't trim effectively, overwrite tail
        try:
            truncated = current[:KNOWLEDGE_CAP_CHARS - len(new_entry) - 100] + "\n...\n" + new_entry + "\n"
            index_path.write_text(truncated)
            return True
        except OSError:
            return False

    # Score sections and trim lowest-weight ones
    scored = []
    for section in sections:
        weight_match = re.search(r"weight[:\s]*([\d.]+)", section)
        w = float(weight_match.group(1)) if weight_match else 0.5
        scored.append((w, section))

    scored.sort(key=lambda x: x[0])  # lowest first

    # Keep removing until size fits
    target_size = KNOWLEDGE_CAP_CHARS - len(new_entry) - 50
    kept = scored.copy()
    while kept:
        total = sum(len(s[1]) for s in kept)
        if total <= target_size:
            break
        kept.pop(0)  # remove lowest weight

    new_content = "\n".join(s[1] for s in kept) + "\n" + new_entry + "\n"
    try:
        index_path.write_text(new_content)
        return True
    except OSError:
        return False


# ── Identity Tier (agent.yaml / specifics) ───────────────────────────

def promote_to_identity(cfg, filename: str, content: str, weight: float) -> bool:
    """
    Promote a finding to identity storage.
    Logs to identity_log.jsonl via _apply_identity_edit (safe, never mutates source files).
    Only writes if weight meets the file's threshold.
    """
    from helpers.registry import _apply_identity_edit
    threshold = cfg.get_identity_weight(filename)
    if weight < threshold:
        return False

    # Map filename to tier for logging
    tier_map = {
        "agent.yaml": "soul",
        "prompts/agent.system.main.specifics.md": "agents",
        "SKILL.md": "memory",
    }
    tier = tier_map.get(filename, "knowledge")
    _apply_identity_edit(cfg, tier, content)
    return True


# ── Cross-Cycle Pattern Detection ──────────────────────────────────

def detect_cross_cycle_patterns(evol_log_path: Path, min_cycles: int = 3) -> List[Dict[str, Any]]:
    """
    Detect patterns recurring across 3+ cycles.
    Auto-promotes to identity at weight 0.85+.
    """
    if not evol_log_path.exists():
        return []

    try:
        entries = [json.loads(l) for l in evol_log_path.read_text().splitlines()[-30:]]
    except (json.JSONDecodeError, OSError):
        return []

    pattern_counts: Dict[str, List[str]] = {}
    for entry in entries:
        phases = entry.get("phases", {})
        reflect_data = phases.get("reflect", {}).get("data", {})
        for pattern in reflect_data.get("patterns", []):
            key = str(pattern).lower().strip()[:80]
            if key:
                pattern_counts.setdefault(key, []).append(entry.get("timestamp", ""))

    cross_cycle = []
    for pattern, timestamps in pattern_counts.items():
        if len(timestamps) >= min_cycles:
            cross_cycle.append({
                "pattern": pattern,
                "occurrences": len(timestamps),
                "first_seen": timestamps[0],
                "last_seen": timestamps[-1],
                "promotion_weight": min(0.85 + (len(timestamps) - min_cycles) * 0.05, 1.0),
            })

    return cross_cycle


def rebuild_knowledge_index(knowledge_dir: Path):
    """Rebuild index.md with decay indicators for all knowledge entries."""
    index_path = knowledge_dir / "index.md"
    now = time.time()

    lines = ["# Knowledge Index\n", f"Generated: {datetime.now().isoformat()}\n"]

    for domain_dir in sorted(knowledge_dir.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith("."):
            continue
        lines.append(f"\n## {domain_dir.name}\n")

        for md_file in sorted(domain_dir.glob("*.md")):
            if md_file.name == "index.md":
                continue
            try:
                content = md_file.read_text()
                weight_match = re.search(r"weight: ([\d.]+)", content)
                date_match = re.search(r"date: (\d{4}-\d{2}-\d{2})", content)
                title_match = re.search(r"title: \"(.+)\"", content)

                title = title_match.group(1) if title_match else md_file.stem
                weight = float(weight_match.group(1)) if weight_match else 0.5

                # Decay indicator emoji
                if weight >= 0.8:
                    indicator = "🔥"
                elif weight >= 0.5:
                    indicator = "🌳"
                elif weight >= 0.25:
                    indicator = "🌿"
                else:
                    indicator = "🕸️"

                lines.append(f"- {indicator} [[{title}]] (w={weight:.2f})\n")
            except OSError:
                pass

    try:
        index_path.write_text("".join(lines))
    except OSError:
        pass
