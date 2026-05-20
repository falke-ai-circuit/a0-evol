"""EVOL Absorb Tool -- read all identity files and recent sessions."""
import os
import json
import time
from helpers.tool import Tool, Response


def _format_absorb_result(result: dict, profile: str) -> str:
    """Format absorb result as readable markdown report."""
    lines = []
    lines.append(f"## 📥 EVOL Absorb — `{profile}`")
    lines.append("")
    status = result.get("status", "?")
    if status == "error":
        lines.append(f"**Error:** {result.get('error', 'unknown')}")
        return "\n".join(lines)
    if status == "skipped":
        lines.append(f"**Skipped:** {result.get('reason', 'unknown')}")
        return "\n".join(lines)

    data = result.get("data", {})
    identity_files = data.get("identity_files", {})
    idle_depth = data.get("idle_depth", "fresh")
    session_summary = data.get("session_summary", "")
    evol_log = data.get("evolution_log", [])

    lines.append(f"**Idle depth:** {idle_depth}  |  **Timestamp:** {data.get('timestamp', '')}")
    lines.append("")

    # Identity files
    lines.append("### Identity Files Read")
    lines.append("")
    lines.append("| File | Size |")
    lines.append("|------|------|")
    for fname, content in sorted(identity_files.items()):
        lines.append(f"| {fname} | {len(content)} chars |")
    if not identity_files:
        lines.append("| — | No identity files found |")
    lines.append("")

    # Recent sessions
    if session_summary:
        lines.append("### Recent Session Activity")
        lines.append("")
        for line in session_summary.split("\n")[:10]:
            if line.strip():
                lines.append(f"> {line.strip()[:200]}")
        lines.append("")

    # Evolution history
    if evol_log:
        lines.append("### Previous Cycles")
        lines.append("")
        for entry in evol_log[-3:]:
            ts = entry.get("timestamp", "")[:19]
            st = entry.get("status", "?")
            dur = entry.get("duration_seconds", 0)
            lines.append(f"- `{ts}` — **{st}** ({dur}s)")
        lines.append("")

    return "\n".join(lines)


class EvolAbsorbTool(Tool):
    async def execute(self, **kwargs) -> Response:
        try:
            from usr.plugins.a0_evol.helpers.config import EvolConfig
            from usr.plugins.a0_evol.helpers.registry import absorb
            cfg = EvolConfig()
            profile = cfg.profile or "unknown"
            result_data = absorb(cfg)
            result = {"status": "ok", "data": result_data}

            evoldir = f'/a0/usr/agents/{profile}/evol'
            os.makedirs(evoldir, exist_ok=True)
            ts = time.strftime('%Y%m%d_%H%M%S')
            filename = f'{evoldir}/absorb_{ts}.json'
            with open(filename, 'w') as f:
                json.dump(result, f, indent=2, default=str)

            markdown = _format_absorb_result(result, profile)
            markdown += f"\n\n📁 Saved: `{filename}`"

            return Response(message=markdown, break_loop=False)
        except Exception as e:
            return Response(message=f"EVOL absorb error: {e}", break_loop=False)
