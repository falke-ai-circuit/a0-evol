"""
EVOL Commands — /evol slash command handler.

Usage:
  /evol status    — show EVOL status
  /evol cycle     — run full cycle
  /evol speak     — trigger express
  /evol reflect   — trigger reflect
  /evol explore   — trigger explore
  /evol memorize  — trigger memory consolidation
  /evol config    — show current config
  /evol material  — show absorbed material
"""

import json
from typing import Optional, Dict, Any


def handle_evol_command(engine, args: str) -> str:
    """
    Handle /evol slash command.

    Args:
        engine: EvolEngine instance
        args: command arguments string

    Returns:
        Formatted response string
    """
    parts = args.strip().split()
    command = parts[0].lower() if parts else "status"
    force = "--force" in parts or "-f" in parts

    try:
        if command == "status":
            result = engine.status()
            return _format_status(result)

        elif command == "cycle":
            result = engine.full_cycle(force=force)
            return _format_result("Full Cycle", result)

        elif command == "speak":
            result = engine.speak(force=force)
            return _format_result("Express", result)

        elif command == "reflect":
            result = engine.reflect(force=force)
            return _format_result("Reflect", result)

        elif command == "explore":
            result = engine.explore(force=force)
            return _format_result("Explore", result)

        elif command == "memorize":
            result = engine.memorize(force=force)
            return _format_result("Memorize", result)

        elif command == "config":
            result = engine.get_config()
            return f"```json\n{json.dumps(result, indent=2)[:2000]}\n```"

        elif command == "material":
            result = engine.material()
            return _format_result("Material", result)

        else:
            return f"Unknown command: {command}\nAvailable: status, cycle, speak, reflect, explore, memorize, config, material"

    except Exception as e:
        return f"Error: {str(e)}"


def _format_status(data: Dict[str, Any]) -> str:
    """Format status output for CLI."""
    lines = [
        f"EVOL Status — {data.get('profile', '?')}",
        f"Enabled: {data.get('enabled', False)}",
        f"Edit mode: {data.get('edit_mode', '?')}",
        f"Phases: {json.dumps(data.get('phases', {}))}",
        f"Cooldown: {data.get('cooldown', '?')}",
        f"Express cooldown: {data.get('express_cooldown', '?')}",
        f"Last cycle: {data.get('last_cycle', 'never')}",
        f"Last express: {data.get('last_express', 'never')}",
        f"Phase counts: {json.dumps(data.get('phase_counts', {}))}",
        f"Heartbeat: {'running' if data.get('heartbeat_running') else 'stopped'}",
    ]
    return "\n".join(lines)


def _format_result(label: str, data: Dict[str, Any]) -> str:
    """Format a phase result for CLI."""
    status = data.get("status", "?")
    if status == "error":
        return f"{label}: ERROR — {data.get('error', 'unknown')}"
    elif status == "skipped":
        return f"{label}: SKIPPED — {data.get('reason', 'unknown')}"
    else:
        inner = data.get("data", {})
        summary = {k: v for k, v in inner.items() if k not in ("raw_response", "data", "circuit_files", "session_summary")}
        return f"{label}: OK\n```json\n{json.dumps(summary, indent=2, default=str)[:1500]}\n```"
