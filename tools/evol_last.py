"""EVOL Last Tool -- display latest EVOL cycle result."""
import os
import json
from helpers.tool import Tool, Response


def _format_last_result(result: dict, profile: str) -> str:
    """Format last cycle result as a readable markdown report."""
    lines = []
    lines.append(f"## 🧬 Latest EVOL Activity — `{profile}`")
    lines.append("")
    status = result.get("status", "?")
    duration = result.get("duration_seconds", 0)
    ts = result.get("timestamp", "")
    lines.append(f"**Status:** {status}  |  **Duration:** {duration}s  |  **Timestamp:** {ts}")
    lines.append("")
    if status == "error":
        lines.append(f"Error: {result.get('error', 'unknown')}")
        return "\n".join(lines)
    if status == "skipped":
        lines.append(f"Reason: {result.get('reason', 'unknown')}")
        return "\n".join(lines)

    phases = result.get("phases", {})
    lines.append("| Phase | Outcome | Details |")
    lines.append("|-------|---------|---------|")
    phase_details = {
        "absorb": ("📥 Absorb", lambda d: f"sources: {d.get('sources_count', 0)}"),
        "reflect": ("🪞 Reflect", lambda d: f"patterns: {d.get('patterns', 0)}, anomalies: {d.get('anomalies', 0)}, bridge signals: {d.get('bridge_signals', 0)}"),
        "explore": ("🌐 Explore", lambda d: f"queries: {len(d.get('queries', []))}, discoveries: {d.get('discoveries', 0)}"),
        "express": ("🗣️ Express", lambda d: f"mood: {d.get('mood', '?')}, insights: {d.get('insights', 0)}"),
        "memorize": ("💾 Memorize", lambda d: f"items scored: {d.get('items_scored', 0)}, applied: {d.get('applied', 0)}, proposals: {d.get('proposed', 0)}"),
    }
    for phase_key in ["absorb", "reflect", "explore", "express", "memorize"]:
        phase = phases.get(phase_key, {})
        if not phase:
            lines.append(f"| {phase_key} | — | — |")
            continue
        pstatus = phase.get("status", "?")
        label, detail_fn = phase_details.get(phase_key, (phase_key, lambda d: ""))
        if pstatus == "skipped":
            reason = phase.get("reason", "unknown")
            lines.append(f"| {label} | skipped | *{reason}* |")
        elif pstatus == "error":
            err = phase.get("error", "?")
            lines.append(f"| {label} | ❌ error | {err} |")
        else:
            detail = detail_fn(phase)
            lines.append(f"| {label} | ✅ ok | {detail} |")

    lines.append("")
    # Express monologue preview if present
    express_phase = phases.get("express", {})
    if express_phase.get("status") == "ok":
        mono = express_phase.get("data", {}).get("monologue", "")
        if mono:
            lines.append(f"> *{mono[:500]}*")
            lines.append("")
    return "\n".join(lines)


class EvolLastTool(Tool):
    async def execute(self, **kwargs) -> Response:
        try:
            from usr.plugins.a0_evol.helpers.config import EvolConfig
            cfg = EvolConfig()
            profile = cfg.profile or "unknown"
            evol_log = os.path.join(cfg.profile_dir, "evol", "evol.jsonl")
            if not os.path.exists(evol_log):
                return Response(
                    message=f"No EVOL activity yet for profile `{profile}`.\nRun `/evol cycle` to trigger.",
                    break_loop=False,
                )
            with open(evol_log, "r") as f:
                lines = f.readlines()
            if not lines:
                return Response(
                    message=f"EVOL log empty for profile `{profile}`.",
                    break_loop=False,
                )
            last = json.loads(lines[-1])
            markdown = _format_last_result(last, profile)
            return Response(message=markdown, break_loop=False)
        except Exception as e:
            return Response(message=f"EVOL last error: {e}", break_loop=False)
