"""
EVOL Engine — Cycle Orchestrator.

Runs the 5-phase cycle: absorb → reflect → explore → express → memorize.
Supports persistent mode (heartbeat + cascading triggers) and session mode (single-shot).

Entry points:
  run_cycle(profile="conductor") — full cycle for persistent mode
  run_session_cycle(profile="coder") — single-shot for subagents

Also: EvolEngine bridge class for tool-access API.
"""

import time
import json
import os
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    from usr.plugins.a0_evol.helpers.config import EvolConfig
    from usr.plugins.a0_evol.helpers.registry import (
        absorb, reflect, explore, express, memorize, _utc_now, _log_cycle_result
    )
except ImportError:
    from config import EvolConfig
    from registry import absorb, reflect, explore, express, memorize, _utc_now


# ═══════════════════════════════════════════════════════════════════
# MODULE-LEVEL FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def run_cycle(
    profile: Optional[str] = None,
    mode: Optional[str] = None,
    force: bool = False,
    skip_phases: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run a complete EVOL cycle for a profile (persistent mode).

    Returns:
        {status, profile, mode, phases: {absorb/reflect/explore/express/memorize}, duration_seconds}
    """
    t_start = time.time()
    skip = set(skip_phases or [])

    try:
        cfg = EvolConfig(profile=profile, mode=mode)
    except Exception as e:
        return {"status": "error", "profile": profile or "unknown", "error": f"Config load failed: {e}"}

    result: Dict[str, Any] = {
        "status": "ok",
        "profile": cfg.profile,
        "mode": cfg.mode,
        "phases": {},
        "duration_seconds": 0,
    }

    if not cfg.enabled:
        return {**result, "status": "skipped", "reason": "EVOL disabled"}

    if not force and not _should_run(cfg):
        return {**result, "status": "skipped", "reason": "cooldown"}

    # ── PHASE 1: ABSORB ──
    absorbed = None
    if "absorb" not in skip and cfg.is_phase_enabled("absorb"):
        try:
            if cfg.mode == "global":
                absorbed = _absorb_global(cfg)
            else:
                absorbed = _run_with_retry(absorb, cfg, phase_name="absorb")
            result["phases"]["absorb"] = {
                "status": "ok",
                "sources_count": len(absorbed.get("circuit_files", {})),
                "data": absorbed,
            }
        except Exception as e:
            result["phases"]["absorb"] = {"status": "error", "error": str(e)}
            return {**result, "status": "error", "error": f"absorb failed: {e}"}
    else:
        absorbed = {"profile": cfg.profile, "mode": cfg.mode, "circuit_files": {}, "session_summary": ""}
        result["phases"]["absorb"] = {"status": "skipped"}

    # ── PHASE 2: REFLECT ──
    if "reflect" not in skip and cfg.is_phase_enabled("reflect"):
        try:
            reflected = _run_with_retry(reflect, cfg, absorbed, phase_name="reflect")
            result["phases"]["reflect"] = {
                "status": "ok",
                "patterns": len(reflected.get("patterns", [])),
                "anomalies": len(reflected.get("anomalies", [])),
                "bridge_signals": len(reflected.get("bridge_signals", [])),
                "data": reflected,
            }
            _run_phase_post_hook(cfg, "reflect", reflected, result)
        except Exception as e:
            result["phases"]["reflect"] = {"status": "error", "error": str(e)}
            reflected = {"patterns": [], "anomalies": [], "bridge_signals": [], "circuit_health": {}}
    else:
        reflected = {"patterns": [], "anomalies": [], "bridge_signals": [], "circuit_health": {}}
        result["phases"]["reflect"] = {"status": "skipped"}

    # ── PHASE 3: EXPLORE ──
    if "explore" not in skip and cfg.is_phase_enabled("explore"):
        try:
            explored = _run_with_retry(explore, cfg, reflected, phase_name="explore")
            result["phases"]["explore"] = {
                "status": "ok",
                "queries": explored.get("queries", []),
                "discoveries": len(explored.get("discoveries", [])),
                "data": explored,
            }
            _run_phase_post_hook(cfg, "explore", explored, result)
        except Exception as e:
            result["phases"]["explore"] = {"status": "error", "error": str(e)}
            explored = {"queries": [], "results": [], "discoveries": []}
    else:
        explored = {"queries": [], "results": [], "discoveries": []}
        result["phases"]["explore"] = {"status": "skipped"}

    # ── PHASE 4: EXPRESS ──
    expressed = None
    if "express" not in skip and cfg.is_phase_enabled("express"):
        if not force and not _express_can_run(cfg):
            result["phases"]["express"] = {"status": "skipped", "reason": "cooldown"}
        else:
            try:
                expressed = _run_with_retry(express, cfg, reflected, explored, phase_name="express")
                result["phases"]["express"] = {
                    "status": "ok",
                    "mood": expressed.get("mood", "unknown"),
                    "insights": len(expressed.get("insights", [])),
                    "data": expressed,
                }
                _touch_marker(cfg, "last_express")
                _run_phase_post_hook(cfg, "express", expressed, result)
            except Exception as e:
                result["phases"]["express"] = {"status": "error", "error": str(e)}
    else:
        result["phases"]["express"] = {"status": "skipped"}

    # ── PHASE 5: MEMORIZE ──
    if "memorize" not in skip and cfg.is_phase_enabled("memorize"):
        try:
            memorized = _run_with_retry(memorize, cfg, reflected, expressed, explored, phase_name="memorize")
            result["phases"]["memorize"] = {
                "status": "ok",
                "items_scored": len(memorized.get("items", [])),
                "applied": len(memorized.get("applied", [])),
                "proposed": len(memorized.get("proposals", [])),
                "data": memorized,
            }
            _run_phase_post_hook(cfg, "memorize", memorized, result)
        except Exception as e:
            result["phases"]["memorize"] = {"status": "error", "error": str(e)}
    else:
        result["phases"]["memorize"] = {"status": "skipped"}

    # ── Finalize ──
    _touch_marker(cfg, "last_cycle")
    result["duration_seconds"] = round(time.time() - t_start, 2)

    # Log cycle to evol.jsonl
    _log_cycle_result(cfg, result)

    return result


def run_session_cycle(
    profile: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run a single-shot EVOL cycle for session mode (subagent task-end).

    Differences from persistent:
      - No cooldown checks
      - No heartbeat, no cascade counters, no idle depth
      - Absorb: latest session + role circuit files only
      - Express: synthesis style
      - Explore: limited queries
      - Memorize: role-scoped — NEVER touches conductor circuit
    """
    t_start = time.time()

    try:
        cfg = EvolConfig(profile=profile)
        cfg.operation_mode = "session"
        cfg.express_style = "synthesis"
        cfg.explore_query_limit = 1
    except Exception as e:
        return {"status": "error", "profile": profile or "unknown", "error": f"Config load failed: {e}"}

    result: Dict[str, Any] = {
        "status": "ok",
        "profile": cfg.profile,
        "mode": "session",
        "phases": {},
        "duration_seconds": 0,
    }

    if not cfg.enabled:
        return {**result, "status": "skipped", "reason": "EVOL disabled"}

    # ── PHASE 1: ABSORB (session-scoped) ──
    if cfg.is_phase_enabled("absorb"):
        try:
            absorbed = _absorb_session(cfg, session_id)
            result["phases"]["absorb"] = {
                "status": "ok",
                "sources_count": len(absorbed.get("circuit_files", {})),
                "data": absorbed,
            }
        except Exception as e:
            result["phases"]["absorb"] = {"status": "error", "error": str(e)}
            return {**result, "status": "error", "error": f"absorb failed: {e}"}
    else:
        absorbed = {"profile": cfg.profile, "circuit_files": {}, "session_summary": ""}
        result["phases"]["absorb"] = {"status": "skipped"}

    # ── PHASE 2: REFLECT ──
    if cfg.is_phase_enabled("reflect"):
        try:
            reflected = _run_with_retry(reflect, cfg, absorbed, phase_name="reflect")
            result["phases"]["reflect"] = {
                "status": "ok",
                "patterns": len(reflected.get("patterns", [])),
                "data": reflected,
            }
        except Exception as e:
            result["phases"]["reflect"] = {"status": "error", "error": str(e)}
            reflected = {"patterns": [], "anomalies": [], "bridge_signals": [], "circuit_health": {}}
    else:
        reflected = {"patterns": [], "anomalies": [], "bridge_signals": [], "circuit_health": {}}
        result["phases"]["reflect"] = {"status": "skipped"}

    # ── PHASE 3: EXPRESS (synthesis style — express before explore in session) ──
    expressed = None
    if cfg.is_phase_enabled("express"):
        try:
            expressed = _run_with_retry(express, cfg, reflected, None,
                                         phase_name="express", style="synthesis")
            result["phases"]["express"] = {
                "status": "ok",
                "style": "synthesis",
                "insights": len(expressed.get("insights", [])),
                "data": expressed,
            }
        except Exception as e:
            result["phases"]["express"] = {"status": "error", "error": str(e)}

    # ── PHASE 4: EXPLORE (limited queries) ──
    explored = {"queries": [], "results": [], "discoveries": []}
    if cfg.is_phase_enabled("explore"):
        try:
            explored = _run_with_retry(explore, cfg, reflected, phase_name="explore", query_limit=1)
            result["phases"]["explore"] = {
                "status": "ok",
                "queries": explored.get("queries", []),
                "discoveries": len(explored.get("discoveries", [])),
                "data": explored,
            }
        except Exception as e:
            result["phases"]["explore"] = {"status": "error", "error": str(e)}

    # ── PHASE 5: MEMORIZE (role-scoped) ──
    if cfg.is_phase_enabled("memorize"):
        try:
            memorized = _run_with_retry(memorize, cfg, reflected, expressed, explored,
                                         phase_name="memorize", scope="role")
            result["phases"]["memorize"] = {
                "status": "ok",
                "applied": len(memorized.get("applied", [])),
                "proposed": len(memorized.get("proposals", [])),
                "data": memorized,
            }
        except Exception as e:
            result["phases"]["memorize"] = {"status": "error", "error": str(e)}
    else:
        result["phases"]["memorize"] = {"status": "skipped"}

    result["duration_seconds"] = round(time.time() - t_start, 2)
    return result


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _safe_read(path) -> str:
    try:
        return Path(path).read_text()
    except (OSError, IOError):
        return ""


def _absorb_session(cfg: EvolConfig, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Session-mode absorb: latest session + role circuit files only."""
    data: Dict[str, Any] = {
        "profile": cfg.profile,
        "timestamp": _utc_now(),
        "session_summary": "",
        "circuit_files": {},
        "evolution_log": [],
        "session_id": session_id,
    }

    for fname in ["SOUL.md", "AGENTS.md", "MEMORY.md"]:
        path = cfg.get_circuit_path(fname)
        content = _safe_read(path)
        if content:
            data["circuit_files"][fname] = content[:6000]

    sessions_dir = Path(cfg.profile_dir) / "sessions"
    if sessions_dir.exists():
        jsonl_files = sorted(
            sessions_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        if jsonl_files:
            try:
                lines = jsonl_files[0].read_text().splitlines()
                msgs = []
                for line in lines[-200:]:
                    try:
                        msg = json.loads(line)
                        role = msg.get("role", "?")
                        content = msg.get("content", "")[:300]
                        if content:
                            msgs.append(f"[{role}] {content}")
                    except (json.JSONDecodeError, KeyError):
                        pass
                data["session_summary"] = "\n".join(msgs[-100:])
            except (OSError, IOError):
                data["session_summary"] = "[session data unavailable]"

    evol_log = Path(cfg.profile_dir) / "evol.jsonl"
    if evol_log.exists():
        try:
            entries = [json.loads(l) for l in evol_log.read_text().splitlines()[-10:]]
            data["evolution_log"] = entries
        except (json.JSONDecodeError, OSError):
            pass

    return data


def _absorb_global(cfg: EvolConfig) -> Dict[str, Any]:
    """Absorb ALL profiles and merge into one combined context."""
    profiles = cfg.global_profiles or [cfg.profile]
    combined: Dict[str, Any] = {
        "profile": "global",
        "mode": "global",
        "timestamp": _utc_now(),
        "circuit_files": {},
        "session_summary": "",
        "evolution_log": [],
        "profiles_absorbed": [],
    }
    for prof in profiles:
        try:
            pc = EvolConfig(profile=prof)
            pc.search_backend = cfg.search_backend
            a = absorb(pc)
            for fn, content in a.get("circuit_files", {}).items():
                combined["circuit_files"][f"{prof}/{fn}"] = content
            if a.get("session_summary"):
                combined["session_summary"] += f"\n[{prof}] {a['session_summary'][:300]}"
            combined["evolution_log"].extend(a.get("evolution_log", [])[-5:])
            combined["profiles_absorbed"].append(prof)
        except Exception:
            pass
    return combined


def _run_with_retry(phase_fn, cfg: EvolConfig, *args, phase_name: str, **kwargs) -> Any:
    """Run a phase function with exponential backoff retry."""
    last_error = None
    for attempt in range(cfg.max_retries_per_phase):
        try:
            return phase_fn(cfg, *args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < cfg.max_retries_per_phase - 1:
                time.sleep(2 ** attempt)
    raise last_error  # type: ignore


def _should_run(cfg: EvolConfig) -> bool:
    """Check cooldown since last cycle."""
    marker = Path(cfg.profile_dir) / "evol" / ".last_cycle"
    if not marker.exists():
        return True
    try:
        last = float(marker.read_text().strip())
        elapsed = (time.time() - last) / 60
        return elapsed >= cfg.cooldown_minutes
    except (ValueError, OSError):
        return True


def _express_can_run(cfg: EvolConfig) -> bool:
    """Check express cooldown."""
    marker = Path(cfg.profile_dir) / "evol" / ".last_express"
    if not marker.exists():
        return True
    try:
        last = float(marker.read_text().strip())
        elapsed = (time.time() - last) / 3600
        return elapsed >= cfg.express_cooldown_hours
    except (ValueError, OSError):
        return True


def _touch_marker(cfg: EvolConfig, name: str):
    """Write timestamp marker file."""
    marker = Path(cfg.profile_dir) / "evol" / f".{name}"
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        marker.write_text(str(time.time()))
    except OSError:
        pass


PHASE_RESULT_KEYS = {
    "absorb": ["circuit_files", "session_summary", "timestamp"],
    "reflect": ["patterns", "anomalies", "recommended_action"],
    "express": ["monologue", "mood", "insights", "portrait_prompt", "circuit_poem", "unanswered"],
    "explore": ["queries", "results", "discoveries"],
    "memorize": ["items", "applied", "proposals"],
}


def _run_phase_post_hook(cfg: EvolConfig, phase: str, phase_data: Dict[str, Any], cycle_result: Dict[str, Any]):
    """Execute a post-phase hook if configured."""
    cmd = cfg.phase_post_commands.get(phase, "")
    if not cmd:
        return

    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, prefix=f"evol-{phase}-") as f:
        json.dump(phase_data, f)
        result_file = f.name

    env = os.environ.copy()
    env["PHASE_RESULT_FILE"] = result_file
    env["EVOL_PROFILE"] = cfg.profile
    env["EVOL_PHASE"] = phase

    known_keys = PHASE_RESULT_KEYS.get(phase, list(phase_data.keys()))
    for key in known_keys:
        val = phase_data.get(key)
        if val is not None:
            if isinstance(val, (list, dict)):
                env[f"PHASE_{key}"] = json.dumps(val)
            else:
                env[f"PHASE_{key}"] = str(val)[:4000]

    try:
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True,
            timeout=180,
            env=env,
        )
        stdout = result.stdout.strip()
        if stdout:
            hook_result = _parse_hook_output(stdout)
            if hook_result:
                phase_result = cycle_result.setdefault("phases", {}).setdefault(phase, {})
                phase_result["media"] = hook_result
    except Exception:
        pass
    finally:
        try:
            os.unlink(result_file)
        except OSError:
            pass


def _parse_hook_output(stdout: str) -> Dict[str, str]:
    """Parse hook stdout — JSON dict or file paths."""
    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v and isinstance(v, str) and os.path.exists(v)}
    except (json.JSONDecodeError, ValueError):
        pass

    media = {}
    for line in stdout.splitlines():
        line = line.strip()
        if line.endswith((".mp4", ".mp3", ".jpg", ".png", ".webp")):
            if line.startswith("MEDIA:"):
                line = line[6:]
            if os.path.exists(line):
                ext = os.path.splitext(line)[1]
                if ext == ".mp4":
                    media["video"] = line
                elif ext == ".mp3":
                    media["voice"] = line
                elif ext in (".jpg", ".png", ".webp"):
                    media["portrait"] = line
    return media


# ═══════════════════════════════════════════════════════════════════
# EvolEngine Bridge
# ═══════════════════════════════════════════════════════════════════

class EvolEngine:
    """Bridge class wrapping EVOL module functions into OOP API for tool access."""

    def __init__(self, config: EvolConfig):
        self.cfg = config
        self.profile = config.profile
        self.mode = config.mode
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cooldowns: Dict[str, float] = {}

        # Phase toggles
        self._absorb_enabled = config.phase_enabled.get("absorb", True)
        self._reflect_enabled = config.phase_enabled.get("reflect", True)
        self._explore_enabled = config.phase_enabled.get("explore", True)
        self._express_enabled = config.phase_enabled.get("express", True)
        self._memorize_enabled = config.phase_enabled.get("memorize", True)
        self._heartbeat_enabled = True

        # Material buffer for heartbeat absorb ticks
        self._material_buffer: List[Dict] = []

        # Cascading counters
        self._phase_counts: Dict[str, int] = {
            "reflect": 0,  # incremented by absorb ticks
            "express": 0,  # incremented by reflect completions
            "explore": 0,  # incremented by express completions
            "memorize": 0,  # incremented by explore completions
        }
        self._load_phase_counts()

    # ── Phase counts persistence ──

    def _load_phase_counts(self):
        path = Path(self.cfg.profile_dir) / "evol" / ".phase_counts.json"
        if path.exists():
            try:
                self._phase_counts = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    def _save_phase_counts(self):
        path = Path(self.cfg.profile_dir) / "evol" / ".phase_counts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(self._phase_counts))
        except OSError:
            pass

    # ── Cooldown helpers ──

    def _check_cooldown(self, name: str, minutes: int = 60) -> bool:
        now = time.time()
        last = self._cooldowns.get(name, 0)
        return (now - last) >= (minutes * 60)

    def _set_cooldown(self, name: str):
        self._cooldowns[name] = time.time()

    # ── Tool methods ──

    def status(self) -> Dict[str, Any]:
        last_cycle_path = Path(self.cfg.profile_dir) / "evol" / ".last_cycle"
        last_express_path = Path(self.cfg.profile_dir) / "evol" / ".last_express"

        def _read_ts(p: Path) -> Optional[str]:
            try:
                ts = float(p.read_text().strip())
                return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except (ValueError, OSError):
                return None

        return {
            "profile": self.cfg.profile,
            "mode": self.cfg.mode,
            "enabled": self.cfg.enabled,
            "edit_mode": self.cfg.edit_mode,
            "phases": self.cfg.phase_enabled,
            "phase_models": {
                phase: {"provider": pm.provider or "default", "model": pm.model or "default"}
                for phase, pm in self.cfg.phase_models.items()
            },
            "cooldown": f"{self.cfg.cooldown_minutes}min",
            "express_cooldown": f"{self.cfg.express_cooldown_hours}h",
            "last_cycle": _read_ts(last_cycle_path),
            "last_express": _read_ts(last_express_path),
            "phase_counts": self._phase_counts,
            "heartbeat_running": self._running,
        }

    def material(self) -> Dict[str, Any]:
        return {
            "profile": self.profile,
            "mode": self.mode,
            "buffer_size": len(self._material_buffer),
            "recent": self._material_buffer[-20:] if self._material_buffer else [],
        }

    def get_config(self) -> Dict[str, Any]:
        return self.cfg.to_dict()

    def speak(self, force: bool = False) -> Dict[str, Any]:
        """Express phase — inner monologue."""
        if not force and not self._express_enabled:
            return {"status": "skipped", "reason": "express disabled"}
        try:
            reflected = {"patterns": [], "anomalies": [], "bridge_signals": [], "circuit_health": {}}
            result = express(self.cfg, reflected)
            self._set_cooldown("express")
            self._phase_counts["explore"] = self._phase_counts.get("explore", 0) + 1
            self._save_phase_counts()
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def reflect(self, force: bool = False) -> Dict[str, Any]:
        """Reflect phase — pattern synthesis."""
        if not force and not self._reflect_enabled:
            return {"status": "skipped", "reason": "reflect disabled"}
        try:
            circuit_files = {}
            session_summary = ""
            if self._material_buffer:
                for tick in self._material_buffer:
                    if tick.get("type") == "absorb_tick":
                        for f in tick.get("files", []):
                            if f not in circuit_files:
                                circuit_files[f] = ""
                        session_summary += tick.get("summary", "")

            absorbed = {
                "profile": self.profile,
                "mode": self.mode,
                "circuit_files": circuit_files,
                "session_summary": session_summary,
            }
            result = reflect(self.cfg, absorbed)
            self._set_cooldown("reflect")
            self._phase_counts["express"] = self._phase_counts.get("express", 0) + 1
            self._save_phase_counts()
            _touch_marker(self.cfg, "last_reflect")
            self._material_buffer.clear()
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def explore(self, force: bool = False, query: str = "") -> Dict[str, Any]:
        """Explore phase — search gaps."""
        if not force and not self._explore_enabled:
            return {"status": "skipped", "reason": "explore disabled"}
        try:
            reflected = {k: v for k, v in ({"patterns": [], "anomalies": [], "bridge_signals": []}).items()}
            result = explore(self.cfg, {"patterns": [], "anomalies": [], "bridge_signals": []})
            self._set_cooldown("explore")
            self._phase_counts["memorize"] = self._phase_counts.get("memorize", 0) + 1
            self._save_phase_counts()
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def full_cycle(self, force: bool = False) -> Dict[str, Any]:
        """Run complete EVOL cycle."""
        if not force and not self._should_run_check():
            return {"status": "skipped", "reason": "cooldown"}
        try:
            result = run_cycle(profile=self.profile, mode=self.mode, force=force)
            self._set_cooldown("cycle")
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def memorize(self, force: bool = False) -> Dict[str, Any]:
        """Standalone memory consolidation."""
        if not force and not self._memorize_enabled:
            return {"status": "skipped", "reason": "memorize disabled"}
        try:
            reflected = {"patterns": [], "anomalies": [], "bridge_signals": []}
            result = memorize(self.cfg, reflected, None, {"discoveries": [], "queries": []})
            self._set_cooldown("memorize")
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def task_end(self, session_id: str = "", profile: str = "") -> Dict[str, Any]:
        """Session-mode EVOL — single-shot cycle for subagent task completion."""
        try:
            target_profile = profile or self.profile
            result = run_session_cycle(profile=target_profile, session_id=session_id or None)
            return {"status": "ok", "data": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _should_run_check(self) -> bool:
        return _should_run(self.cfg)

    # ── Heartbeat ──

    def _heartbeat_loop(self):
        """Background loop: absorb tick every 15 minutes, evaluate cascading triggers."""
        while self._running:
            try:
                self._absorb_tick()
                self._evaluate_triggers()
            except Exception:
                pass
            time.sleep(900)  # 15 minutes

    def _absorb_tick(self):
        """Light absorb tick — increment reflect counter."""
        try:
            ab = absorb(self.cfg)
            self._material_buffer.append({
                "type": "absorb_tick",
                "timestamp": _utc_now(),
                "files": list(ab.get("circuit_files", {}).keys()),
                "summary": ab.get("session_summary", "")[:1000],
            })
            self._phase_counts["reflect"] = self._phase_counts.get("reflect", 0) + 1
            self._save_phase_counts()
        except Exception:
            pass

    def _evaluate_triggers(self):
        """Evaluate cascading counters against thresholds."""
        triggers = {
            "reflect": ("reflect", self._reflect_enabled),
            "express": ("express", self._express_enabled),
            "explore": ("explore", self._explore_enabled),
            "memorize": ("memorize", self._memorize_enabled),
        }

        for phase_key, (engine_method, enabled) in triggers.items():
            threshold = self.cfg.phase_triggers.get(phase_key, 3)
            count = self._phase_counts.get(phase_key, 0)
            if enabled and count >= threshold:
                try:
                    method = {
                        "reflect": self.reflect,
                        "express": self.speak,
                        "explore": self.explore,
                        "memorize": self.memorize,
                    }.get(engine_method)
                    if method:
                        method(force=True)
                    self._phase_counts[phase_key] = 0
                    self._save_phase_counts()
                except Exception:
                    pass

        # Idle fallback: if idle > 6h AND last EVOL > 24h → force one deep cycle
        last_cycle_path = Path(self.cfg.profile_dir) / "evol" / ".last_cycle"
        if last_cycle_path.exists():
            try:
                last_cycle = float(last_cycle_path.read_text().strip())
                hours_since = (time.time() - last_cycle) / 3600
                if hours_since >= self.cfg.fallback_cycle_hours:
                    self.full_cycle(force=True)
            except (ValueError, OSError):
                pass

    def start(self):
        """Start heartbeat daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop heartbeat daemon."""
        self._running = False

    def _phase_state(self) -> Dict[str, Any]:
        return self._phase_counts

    def _get_prompts(self) -> Dict[str, str]:
        return getattr(self, '_custom_prompts', {})

    def _build_status(self) -> Dict[str, Any]:
        return self.status()
