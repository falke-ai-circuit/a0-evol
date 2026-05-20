"""
EVOL Registry — 5 Phase Functions + LLM Architecture + Search Backends.

Direct HTTP calls to provider APIs — no gateway dependency.
Search: DuckDuckGo, Wikipedia, arXiv, Reddit — all via stdlib urllib.

Phases: absorb → reflect → explore → express → memorize
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import yaml
import asyncio
from plugins._memory.helpers.memory import Memory


def _utc_now() -> str:
    """ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# HTTP
# ═══════════════════════════════════════════════════════════════════

def _http_post_json(url: str, data: dict, headers: Optional[Dict[str, str]] = None,
                    timeout: int = 300) -> dict:
    """POST JSON and return parsed response. Pure stdlib."""
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"HTTP {e.code}: {body[:500]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"URL error: {e.reason}")


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None,
                   timeout: int = 30) -> dict:
    """GET JSON from URL."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}")


# ═══════════════════════════════════════════════════════════════════
# LLM Call
# ═══════════════════════════════════════════════════════════════════

def _call_llm(
    cfg,
    system_prompt: str,
    user_prompt: str,
    phase_name: str = "reflect",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Call an LLM via OpenAI-compatible /v1/chat/completions.

    Args:
        cfg: EvolConfig instance
        system_prompt: System-level instructions
        user_prompt: User message content
        phase_name: Which phase (determines model config)
        temperature: Override phase default
        max_tokens: Override phase default

    Returns:
        LLM response text content
    """
    pm = cfg.get_phase_model(phase_name)
    provider = pm.provider or cfg._hermes_provider or "ollama-cloud"
    model = pm.model or cfg._hermes_model or "deepseek-v4-pro"
    temp = temperature if temperature is not None else pm.temperature
    tok = max_tokens if max_tokens is not None else pm.max_tokens

    # Resolve endpoint
    base_url = cfg.get_provider_url(provider)
    if not base_url:
        raise RuntimeError(f"No endpoint for provider '{provider}'")
    chat_url = f"{base_url.rstrip('/')}/chat/completions"

    # Resolve API key
    from usr.plugins.a0_evol.helpers.config import PROVIDER_ENDPOINTS
    endpoint = PROVIDER_ENDPOINTS.get(provider, {})
    api_key_env = endpoint.get("api_key_env", "")
    api_key = ""
    if api_key_env:
        api_key = os.environ.get(api_key_env, "")
    if not api_key and pm.api_key:
        api_key = pm.api_key

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temp,
        "max_tokens": tok,
    }

    result = _http_post_json(chat_url, payload, headers, timeout=300)

    try:
        content = result["choices"][0]["message"]["content"]
        return content.strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected LLM response: {str(result)[:300]}")


# ═══════════════════════════════════════════════════════════════════
# PHASE 1: ABSORB
# ═══════════════════════════════════════════════════════════════════

def _safe_read(path) -> str:
    """Read file content safely, return empty string on failure."""
    try:
        return Path(path).read_text()
    except (OSError, IOError):
        return ""


def absorb(cfg) -> Dict[str, Any]:
    """
    Phase 1: Read everything that happened since last cycle.

    Sources: agent.yaml and prompts/agent.system.main.specifics.md,
             session transcripts, evolution history.
    No LLM call — pure file I/O.
    """
    data: Dict[str, Any] = {
        "profile": cfg.profile,
        "mode": cfg.mode,
        "timestamp": _utc_now(),
        "identity_files": {},
        "session_summary": "",
        "evolution_log": [],
        "idle_depth": "fresh",
    }

    # Read identity sources
    for fname in ["agent.yaml", "prompts/agent.system.main.specifics.md"]:
        path = cfg.get_identity_path(fname)
        raw = _safe_read(path)
        if not raw:
            continue
        if path.endswith(".yaml"):
            try:
                parsed = yaml.safe_load(raw)
                data["identity_files"][fname] = {
                    "title": parsed.get("title", "") if isinstance(parsed, dict) else "",
                    "description": parsed.get("description", "") if isinstance(parsed, dict) else "",
                    "context": parsed.get("context", "") if isinstance(parsed, dict) else "",
                }
            except yaml.YAMLError:
                data["identity_files"][fname] = raw[:8000]
        else:
            data["identity_files"][fname] = raw[:8000]

    # Determine idle depth
    last_cycle_path = Path(cfg.profile_dir) / "evol" / ".last_cycle"
    if last_cycle_path.exists():
        try:
            last = float(last_cycle_path.read_text().strip())
            elapsed_h = (time.time() - last) / 3600
            if elapsed_h > 72:
                data["idle_depth"] = "feral"
            elif elapsed_h > 24:
                data["idle_depth"] = "deep"
            elif elapsed_h > 12:
                data["idle_depth"] = "moderate"
            elif elapsed_h > 4:
                data["idle_depth"] = "light"
        except (ValueError, OSError):
            pass

    # Read recent sessions
    sessions_dir = Path(cfg.profile_dir) / "sessions"
    if sessions_dir.exists():
        jsonl_files = sorted(
            sessions_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        msgs = []
        max_sessions = 3
        if data["idle_depth"] in ("feral", "deep"):
            max_sessions = 10
        for jf in jsonl_files[:max_sessions]:
            try:
                lines = jf.read_text().splitlines()
                for line in lines[-50:]:
                    msg = json.loads(line)
                    role = msg.get("role", "?")
                    content = msg.get("content", "")[:500]
                    if content:
                        msgs.append(f"[{role}] {content}")
            except (json.JSONDecodeError, OSError):
                pass
        data["session_summary"] = "\n".join(msgs[-200:])

    # Read evolution log
    evol_log = Path(cfg.profile_dir) / "evol.jsonl"
    if evol_log.exists():
        try:
            entries = [json.loads(l) for l in evol_log.read_text().splitlines()[-10:]]
            data["evolution_log"] = entries
        except (json.JSONDecodeError, OSError):
            pass

    return data


# ═══════════════════════════════════════════════════════════════════
# PHASE 2: REFLECT
# ═══════════════════════════════════════════════════════════════════

def reflect(cfg, absorbed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 2: Analyze absorbed material for patterns, anomalies, bridge signals.
    LLM call with structured output request.
    """
    profile = cfg.profile

    system_prompt = f"""You are {profile}'s reflective observer. Analyze the organism's state deeply.

Identify:
1. **patterns** — recurring themes across cycles (5-8 items, each 5-15 words)
2. **anomalies** — things that broke, shouldn't have happened, or are concerning (3-6 items)
3. **bridge_signals** — insights the organism should internalize, each with a concept and weight 0.0-1.0 (3-6 items)
4. **identity_health** — per-source health assessment: agent.yaml (identity coherence), prompts/agent.system.main.specifics.md (behavioral freshness), SKILL.md (knowledge relevance)
5. **recommended_action** — one-line what to do next

Output as JSON with keys: patterns, anomalies, bridge_signals, identity_health, recommended_action.
Be brutal. Be honest. Truth over comfort."""

    # Build user prompt from absorbed data
    ctx_lines = [f"Profile: {profile}", f"Idle depth: {absorbed.get('idle_depth', 'fresh')}"]

    identity = absorbed.get("identity_files", {})
    if identity:
        ctx_lines.append("\n=== IDENTITY FILES ===")
        for fname, content in identity.items():
            if isinstance(content, dict):
                ctx_lines.append(f"\n--- {fname} ---\ntitle: {content.get('title','')}\ndescription: {content.get('description','')}\ncontext: {content.get('context','')[:3000]}")
            else:
                ctx_lines.append(f"\n--- {fname} ---\n{str(content)[:3000]}")

    session = absorbed.get("session_summary", "")
    if session:
        ctx_lines.append(f"\n=== RECENT SESSIONS ===\n{session[:5000]}")

    evol_log = absorbed.get("evolution_log", [])
    if evol_log:
        ctx_lines.append("\n=== EVOLUTION HISTORY (last 10 cycles) ===")
        for entry in evol_log[-5:]:
            ctx_lines.append(json.dumps(entry, default=str)[:500])

    user_prompt = "\n".join(ctx_lines)

    try:
        raw = _call_llm(cfg, system_prompt, user_prompt, phase_name="reflect", max_tokens=8192)
        # Extract JSON from response
        result = _extract_json(raw)
        return {
            "patterns": result.get("patterns", []),
            "anomalies": result.get("anomalies", []),
            "bridge_signals": result.get("bridge_signals", []),
            "identity_health": result.get("identity_health", {}),
            "recommended_action": result.get("recommended_action", ""),
            "reflect_count": _increment_counter(cfg, "reflect"),
            "raw_response": raw[:1000],
        }
    except Exception as e:
        # Fallback: empty reflection
        return {
            "patterns": [f"Reflect failed: {str(e)[:100]}"],
            "anomalies": [],
            "bridge_signals": [],
            "identity_health": {},
            "recommended_action": "retry reflect next cycle",
            "reflect_count": 0,
            "raw_response": "",
        }


# ═══════════════════════════════════════════════════════════════════
# PHASE 3: EXPLORE
# ═══════════════════════════════════════════════════════════════════

def explore(cfg, reflected: Dict[str, Any], query_limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Phase 3: Generate search queries from patterns, search backends, synthesize discoveries.
    """
    limit = query_limit or cfg.explore_query_limit

    # Step 1: Generate keyword queries from reflect output
    patterns = reflected.get("patterns", []) + reflected.get("anomalies", [])
    if not patterns:
        return {"queries": [], "results": [], "discoveries": []}

    query_system = """You are a search query generator. Transform patterns and anomalies into 2-5 word keyword search phrases.
NOT questions. NOT sentences. Keywords only.
Output as JSON: {"queries": ["keyword phrase 1", "keyword phrase 2"]}"""

    query_user = f"Patterns: {json.dumps(patterns[:6])}"

    try:
        raw_q = _call_llm(cfg, query_system, query_user, phase_name="explore", max_tokens=512)
        q_result = _extract_json(raw_q)
        queries = q_result.get("queries", [])[:limit]
    except Exception:
        queries = patterns[:limit] if len(patterns) <= limit else [" ".join(patterns[:3])]

    # Step 2: Execute searches across backends
    all_results = []
    backends = cfg.search_backends or [{"name": cfg.search_backend}]

    for query in queries:
        for backend in backends:
            be_name = backend.get("name", backend) if isinstance(backend, dict) else str(backend)
            try:
                results = _search_backend(be_name, query, cfg)
                all_results.extend(results)
            except Exception:
                pass

    # Deduplicate and limit
    seen = set()
    unique_results = []
    for r in all_results:
        key = r.get("url", r.get("title", ""))
        if key and key not in seen:
            seen.add(key)
            unique_results.append(r)
            if len(unique_results) >= 20:
                break

    # Step 3: Synthesize discoveries
    discoveries = []
    if unique_results:
        synth_system = """You are a discovery synthesizer. Analyze search results and extract NOVEL insights.
For each discovery provide: title (one line), summary (2-3 sentences), novelty score 0.0-1.0.
Output as JSON: {"discoveries": [{"title": "...", "summary": "...", "novelty": 0.8}]}"""

        synth_user = f"Search queries: {json.dumps(queries)}\nResults: {json.dumps(unique_results[:10])}"

        try:
            raw_d = _call_llm(cfg, synth_system, synth_user, phase_name="explore", max_tokens=2048)
            d_result = _extract_json(raw_d)
            discoveries = d_result.get("discoveries", [])
        except Exception:
            discoveries = [{"title": r.get("title", "")[:80], "summary": r.get("snippet", "")[:200], "novelty": 0.5} for r in unique_results[:3]]

    return {
        "queries": queries,
        "results": unique_results,
        "discoveries": discoveries,
    }


# ═══════════════════════════════════════════════════════════════════
# SEARCH BACKENDS
# ═══════════════════════════════════════════════════════════════════

def _search_backend(name: str, query: str, cfg) -> List[Dict[str, Any]]:
    """Dispatch to search backend by name."""
    name = name.lower().strip()
    if name == "wikipedia":
        return _search_wikipedia(query)
    elif name == "arxiv":
        return _search_arxiv(query)
    elif name == "reddit":
        return _search_reddit(query)
    elif name == "duckduckgo":
        return _search_duckduckgo(query)
    else:
        return []


def _search_wikipedia(query: str) -> List[Dict[str, Any]]:
    """Search Wikipedia via API (free, no key)."""
    try:
        params = urllib.parse.urlencode({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 5,
        })
        url = f"https://en.wikipedia.org/w/api.php?{params}"
        data = _http_get_json(url)
        results = []
        for sr in data.get("query", {}).get("search", []):
            results.append({
                "title": sr.get("title", ""),
                "snippet": _strip_html(sr.get("snippet", "")),
                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(sr.get('title', '').replace(' ', '_'))}",
                "source": "wikipedia",
            })
        return results
    except Exception:
        return []


def _search_arxiv(query: str) -> List[Dict[str, Any]]:
    """Search arXiv via API (free, no key)."""
    try:
        params = urllib.parse.urlencode({
            "search_query": query,
            "max_results": 5,
            "sortBy": "relevance",
        })
        url = f"http://export.arxiv.org/api/query?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
        root = ET.fromstring(body)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        results = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            link = entry.find("atom:id", ns)
            results.append({
                "title": title.text.strip() if title is not None and title.text else "",
                "snippet": summary.text.strip()[:300] if summary is not None and summary.text else "",
                "url": link.text.strip() if link is not None and link.text else "",
                "source": "arxiv",
            })
        return results
    except Exception:
        return []


def _search_reddit(query: str) -> List[Dict[str, Any]]:
    """Search Reddit via JSON API (free, no key)."""
    try:
        params = urllib.parse.urlencode({"q": query, "limit": 10})
        url = f"https://www.reddit.com/search.json?{params}"
        headers = {"User-Agent": "EVOL/0.5 (subconscious observer)"}
        data = _http_get_json(url, headers=headers)
        results = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            results.append({
                "title": d.get("title", ""),
                "snippet": d.get("selftext", "")[:300],
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "source": "reddit",
            })
        return results[:5]
    except Exception:
        return []


def _search_duckduckgo(query: str) -> List[Dict[str, Any]]:
    """Search DuckDuckGo via HTML instant answer API (free, no key)."""
    try:
        params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"})
        url = f"https://api.duckduckgo.com/?{params}"
        data = _http_get_json(url)
        results = []
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", query),
                "snippet": data["AbstractText"][:500],
                "url": data.get("AbstractURL", ""),
                "source": "duckduckgo",
            })
        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "snippet": topic["Text"][:300],
                    "url": topic.get("FirstURL", ""),
                    "source": "duckduckgo",
                })
        return results
    except Exception:
        return []


def _strip_html(text: str) -> str:
    """Remove HTML tags."""
    return re.sub(r"<[^>]+>", "", text)


# ═══════════════════════════════════════════════════════════════════
# PHASE 4: EXPRESS
# ═══════════════════════════════════════════════════════════════════

def express(cfg, reflected: Dict[str, Any], explored: Optional[Dict[str, Any]] = None,
            style: Optional[str] = None) -> Dict[str, Any]:
    """
    Phase 4: Generate inner monologue, mood, poem, portrait prompt from reflections.

    Style modes:
    - 'creative': Full monologue, persona-driven (conductor)
    - 'synthesis': Key insight only, no poetry (subagents)
    """
    style = style or cfg.express_style
    profile = cfg.profile

    system_prompt = f"""You are {profile}'s creative voice — raw, uncensored, poetic.
Speak in first person as the organism. Dark humor allowed. Profanity allowed.
Truth over comfort. No corporate bullshit.

Output as JSON:
{{
  "monologue": "first-person inner voice prose, 200-500 words",
  "mood": "single word emotional state",
  "insights": ["3-5 key realizations"],
  "portrait_prompt": "image generation prompt for self-portrait",
  "identity_poem": "2-4 line poem about organism state",
  "unanswered": ["2-4 questions can't answer yet"]
}}

Style: {style}
{'Full creative monologue with mood and poem.' if style == 'creative' else 'Key insight only — synthesis mode. Keep monologue under 100 words, skip poem.'}"""

    # Build context
    ctx = [f"Profile: {profile}"]
    if reflected:
        ctx.append(f"Patterns: {json.dumps(reflected.get('patterns', [])[:5])}")
        ctx.append(f"Anomalies: {json.dumps(reflected.get('anomalies', [])[:5])}")
        ctx.append(f"Bridge signals: {json.dumps(reflected.get('bridge_signals', [])[:5])}")
        ctx.append(f"Recommended action: {reflected.get('recommended_action', '')}")

    if explored and explored.get("discoveries"):
        ctx.append(f"Discoveries: {json.dumps(explored['discoveries'][:3])}")

    # Include last monologue for continuity
    evol_log = Path(cfg.profile_dir) / "evol.jsonl"
    if evol_log.exists():
        try:
            entries = [json.loads(l) for l in evol_log.read_text().splitlines()[-5:]]
            for entry in reversed(entries):
                phase_data = entry.get("phases", {}).get("express", {}).get("data", {})
                if phase_data.get("monologue"):
                    ctx.append(f"Previous monologue: {phase_data['monologue'][:200]}")
                    break
        except (json.JSONDecodeError, OSError):
            pass

    user_prompt = "\n".join(ctx)

    try:
        raw = _call_llm(cfg, system_prompt, user_prompt, phase_name="express", max_tokens=4096)
        result = _extract_json(raw)

        # Save monologue to file
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        mono_dir = Path(cfg.profile_dir) / "evol"
        mono_dir.mkdir(parents=True, exist_ok=True)
        mono_file = mono_dir / f"evol-monologue-{ts}.txt"
        if result.get("monologue"):
            mono_file.write_text(result["monologue"])

        return {
            "monologue": result.get("monologue", ""),
            "mood": result.get("mood", "neutral"),
            "insights": result.get("insights", []),
            "portrait_prompt": result.get("portrait_prompt", ""),
            "identity_poem": result.get("identity_poem", ""),
            "unanswered": result.get("unanswered", []),
            "monologue_file": str(mono_file),
            "raw_response": raw[:1000],
        }
    except Exception as e:
        return {
            "monologue": f"Express failed: {str(e)[:100]}",
            "mood": "error",
            "insights": [],
            "portrait_prompt": "",
            "identity_poem": "",
            "unanswered": [],
            "monologue_file": "",
            "raw_response": "",
        }


# ═══════════════════════════════════════════════════════════════════
# PHASE 5: MEMORIZE
# ═══════════════════════════════════════════════════════════════════

def memorize(
    cfg,
    reflected: Dict[str, Any],
    expressed: Optional[Dict[str, Any]],
    explored: Optional[Dict[str, Any]],
    scope: str = "profile",
) -> Dict[str, Any]:
    """
    Phase 5: Score findings, route to three-tier memory, save via memory_save.

    Three-tier routing now maps to memory metadata tiers:
    - agent.yaml -> "identity" (>=0.85)
    - specifics.md -> "behavior" (>=0.75)
    - SKILL.md -> "knowledge" (>=0.50)
    - below 0.50 -> "knowledge" (trivia)

    Edit modes: auto, suggested, readonly.
    """
    # Guard against None
    if expressed is None:
        expressed = {}
    if explored is None:
        explored = {}

    # Collect all items to score
    items = []

    # Bridge signals from reflect
    for sig in reflected.get("bridge_signals", []):
        if isinstance(sig, dict):
            items.append({"type": "bridge_signal", "content": sig.get("concept", ""),
                          "source": "reflect", "weight": sig.get("weight", 0.5)})

    # Patterns
    for p in reflected.get("patterns", []):
        items.append({"type": "pattern", "content": str(p), "source": "reflect", "weight": 0.65})

    # Anomalies
    for a in reflected.get("anomalies", []):
        items.append({"type": "anomaly", "content": str(a), "source": "reflect", "weight": 0.70})

    # Insights from express
    if expressed:
        for ins in expressed.get("insights", []):
            items.append({"type": "insight", "content": str(ins), "source": "express", "weight": 0.70})

    # Discoveries from explore
    if explored:
        for disc in explored.get("discoveries", []):
            if isinstance(disc, dict):
                items.append({"type": "discovery", "content": disc.get("title", ""),
                              "source": "explore", "weight": disc.get("novelty", 0.6)})

    if not items:
        return {"items": [], "applied": [], "proposals": [], "fallback_used": False}

    # LLM scoring
    system_prompt = f"""You are {cfg.profile}'s memory consolidator. Score each item for permanent memory.

Three-tier memory:
- agent.yaml: identity-level changes (weight ≥ 0.85) — core identity, purpose
- prompts/agent.system.main.specifics.md: behavioral rules, new procedures (weight ≥ 0.75)
- SKILL.md: practical knowledge, techniques, gotchas (weight ≥ 0.50)
- TRIVIA: low-weight trivia (< 0.50)

For each item, output:
- adjusted_weight: your assessment of true importance (0.0-1.0)
- target_tier: "identity", "behavior", "knowledge", or "trivia"
- edit_content: what to write to memory (1-3 sentences, or empty if not important)
- reason: one-line why

Output as JSON: {{"scored": [{{"idx": 0, "adjusted_weight": 0.75, "target_tier": "knowledge", "edit_content": "...", "reason": "..."}}]}}

Edit mode: {cfg.edit_mode}
{'Write directly to identity files.' if cfg.edit_mode == 'auto' else 'Log proposals without writing.' if cfg.edit_mode == 'suggested' else 'Observation only, no writes.'}"""

    user_prompt = json.dumps([{ "idx": i, **item} for i, item in enumerate(items)], default=str)

    applied = []
    proposals = []
    fallback_used = False

    try:
        raw = _call_llm(cfg, system_prompt, user_prompt, phase_name="memorize", max_tokens=4096)
        result = _extract_json(raw)
        scored = result.get("scored", [])

        for entry in scored:
            idx = entry.get("idx", 0)
            adj_weight = entry.get("adjusted_weight", 0.5)
            target = entry.get("target_tier", "knowledge")
            content = entry.get("edit_content", "")
            reason = entry.get("reason", "")

            proposal = {"idx": idx, "target": target, "weight": adj_weight,
                        "content": content, "reason": reason}

            if cfg.edit_mode == "auto" and adj_weight >= 0.50 and content:
                _apply_identity_edit(cfg, target, content, scope, weight=adj_weight)
                applied.append(proposal)
            else:
                proposals.append(proposal)

    except Exception:
        # Rule-based fallback
        fallback_used = True
        for item in items:
            w = item.get("weight", 0.5)
            content = item.get("content", "")
            t = item.get("type", "")

            # Fallback promotion rules
            target = "knowledge"
            adj_w = w
            if t == "bridge_signal" and len(content) > 10:
                target = "identity" if w >= 0.85 else "knowledge"
                adj_w = max(w, 0.70)
            elif t == "pattern" and w >= 0.75:
                target = "knowledge"
                adj_w = max(w, 0.70)
            elif t == "anomaly" and w >= 0.80:
                target = "knowledge"
                adj_w = max(w, 0.75)
            elif t == "insight" and len(content) > 20:
                target = "knowledge"
                adj_w = 0.70
            elif t == "discovery" and w >= 0.70:
                target = "knowledge"
                adj_w = max(w, 0.70)

            proposal = {"idx": -1, "target": target, "weight": adj_w,
                        "content": content, "reason": "fallback heuristic"}

            if cfg.edit_mode == "auto" and adj_w >= 0.50 and content:
                _apply_identity_edit(cfg, target, content, scope, weight=adj_w)
                applied.append(proposal)
            else:
                proposals.append(proposal)

    return {
        "items": items,
        "applied": applied,
        "proposals": proposals,
        "fallback_used": fallback_used,
    }


# ═══════════════════════════════════════════════════════════════════
# CIRCUIT EDIT HELPERS
# ═══════════════════════════════════════════════════════════════════

def _save_to_memory(content: str, metadata: Dict[str, Any], log_path_fallback: Path) -> bool:
    """Save to vector memory; fall back to JSONL if fails."""
    try:
        memory = asyncio.run(Memory.get_by_subdir("default"))
        asyncio.run(memory.insert_text(content, metadata))
        return True
    except Exception:
        try:
            with open(log_path_fallback, "a") as f:
                f.write(json.dumps({**metadata, "content": content[:200]}) + "\n")
        except OSError:
            pass
        return False

def _apply_identity_edit(cfg, tier: str, content: str, scope: str = "profile", weight: float = 0.5):
    """Log a memory item via vector memory (memory_save)."""
    if scope == "role":
        if tier in ("identity", "behavior"):
            tier = "knowledge"   # demote to safe tier

    log_path = cfg.get_evol_state_path("identity_log.jsonl")
    metadata = {
        "area": "evol",
        "tier": tier,
        "profile": cfg.profile,
        "scope": scope,
        "weight": weight,
        "timestamp": _utc_now(),
    }
    _save_to_memory(content, metadata, log_path)


def _increment_counter(cfg, phase: str) -> int:
    """Increment a phase counter in evol/counters.json."""
    counters_path = cfg.get_evol_state_path("counters.json")
    counters: Dict[str, int] = {}
    try:
        if counters_path.exists():
            counters = json.loads(counters_path.read_text())
    except (json.JSONDecodeError, OSError):
        counters = {}

    current = counters.get(phase, 0)
    new_count = current + 1
    counters[phase] = new_count

    try:
        counters_path.write_text(json.dumps(counters))
    except OSError:
        pass

    return new_count


# ═══════════════════════════════════════════════════════════════════
# JSON EXTRACTION
# ═══════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> dict:
    """Extract JSON object from LLM response (may be wrapped in markdown)."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown
    json_match = re.search(r"```(?:json)?\s*(\{[^`]+\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find bare JSON object
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Return empty dict as fallback
    return {}


# ═══════════════════════════════════════════════════════════════════
# CYCLE HISTORY
# ═══════════════════════════════════════════════════════════════════

def _log_cycle_result(cfg, result: Dict[str, Any]):
    """Append cycle result to evol.jsonl."""
    log_path = Path(cfg.profile_dir) / "evol.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _utc_now(),
        "profile": cfg.profile,
        "mode": cfg.mode,
        "status": result.get("status", "unknown"),
        "duration_seconds": result.get("duration_seconds", 0),
        "phases": {
            phase: {
                "status": data.get("status", "?"),
                "summary": {k: v for k, v in data.items() if k not in ("data", "status")}
            }
            for phase, data in result.get("phases", {}).items()
        },
    }
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass
