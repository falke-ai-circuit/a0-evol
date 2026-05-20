"""EVOL Reflect Tool -- trigger reflect phase (pattern detection)."""
import os
import json
import time
from helpers.tool import Tool, Response


def _format_reflect_result(result: dict, profile: str) -> str:
    lines = []
    lines.append(f"## 🪞 EVOL Reflect — `{profile}`")
    lines.append("")
    status = result.get("status", "?")
    if status == "error":
        lines.append(f"**Error:** {result.get('error', 'unknown')}")
        return "\n".join(lines)
    if status == "skipped":
        lines.append(f"**Skipped:** {result.get('reason', 'unknown')}")
        return "\n".join(lines)
    data = result.get("data", {})
    patterns = data.get("patterns", [])
    anomalies = data.get("anomalies", [])
    bridge_signals = data.get("bridge_signals", [])
    health = data.get("identity_health", {})
    action = data.get("recommended_action", "")
    lines.append(f"**Patterns:** {len(patterns)}  |  **Anomalies:** {len(anomalies)}  |  **Bridge Signals:** {len(bridge_signals)}")
    lines.append("")
    if patterns:
        lines.append("### Patterns Detected")
        for p in patterns[:5]:
            lines.append(f"- {str(p)[:200]}")
        lines.append("")
    if anomalies:
        lines.append("### Anomalies")
        for a in anomalies[:5]:
            lines.append(f"- {str(a)[:200]}")
        lines.append("")
    if bridge_signals:
        lines.append("### Bridge Signals")
        for s in bridge_signals[:5]:
            if isinstance(s, dict):
                concept = s.get("concept", "")
                weight = s.get("weight", 0)
                lines.append(f"- `{weight:.2f}` — {concept[:200]}")
            else:
                lines.append(f"- {str(s)[:200]}")
        lines.append("")
    if health:
        lines.append("### Circuit Health")
        for k, v in health.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")
    if action:
        lines.append(f"**Recommended Action:** {action}")
        lines.append("")
    return "\n".join(lines)


class EvolReflectTool(Tool):
    async def execute(self, force: bool = False, **kwargs) -> Response:
        try:
            from usr.plugins.a0_evol.helpers.config import EvolConfig
            from usr.plugins.a0_evol.helpers.engine import EvolEngine
            cfg = EvolConfig()
            engine = EvolEngine(cfg)
            result = engine.reflect(force=force)
            profile = engine.cfg.profile or os.environ.get('EVOL_PROFILE', 'unknown')
            evoldir = f'/a0/usr/agents/{profile}/evol'
            os.makedirs(evoldir, exist_ok=True)
            ts = time.strftime('%Y%m%d_%H%M%S')
            filename = f'{evoldir}/reflect_{ts}.json'
            with open(filename, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            markdown = _format_reflect_result(result, profile)
            markdown += f"\n\n📁 Saved: `{filename}`"
            return Response(message=markdown, break_loop=False)
        except Exception as e:
            return Response(message=f"EVOL reflect error: {e}", break_loop=False)
