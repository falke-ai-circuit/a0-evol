"""EVOL Memorize Tool -- trigger memory consolidation phase."""
import os
import json
import time
from helpers.tool import Tool, Response


def _format_memorize_result(result: dict, profile: str) -> str:
    lines = []
    lines.append(f"## 💾 EVOL Memorize — `{profile}`")
    lines.append("")
    status = result.get("status", "?")
    if status == "error":
        lines.append(f"**Error:** {result.get('error', 'unknown')}")
        return "\n".join(lines)
    if status == "skipped":
        lines.append(f"**Skipped:** {result.get('reason', 'unknown')}")
        return "\n".join(lines)
    data = result.get("data", {})
    items = data.get("items", [])
    applied = data.get("applied", [])
    proposals = data.get("proposals", [])
    fallback = data.get("fallback_used", False)
    lines.append(f"**Items scored:** {len(items)}  |  **Applied:** {len(applied)}  |  **Proposed:** {len(proposals)}  |  **Fallback used:** {fallback}")
    lines.append("")
    if applied:
        lines.append("### Applied to Circuit Files")
        for a in applied[:5]:
            target = a.get("target", "?")
            content = a.get("content", "")[:150]
            weight = a.get("weight", 0)
            lines.append(f"- `{weight:.2f}` → **{target}**: {content}")
        lines.append("")
    if proposals:
        lines.append("### Proposed (Pending)")
        for p in proposals[:5]:
            target = p.get("target", "?")
            content = p.get("content", "")[:150]
            weight = p.get("weight", 0)
            reason = p.get("reason", "")[:80]
            lines.append(f"- `{weight:.2f}` → **{target}**: {content} *({reason})*")
        lines.append("")
    return "\n".join(lines)


class EvolMemorizeTool(Tool):
    async def execute(self, force: bool = False, **kwargs) -> Response:
        try:
            from usr.plugins.a0_evol.helpers.config import EvolConfig
            from usr.plugins.a0_evol.helpers.engine import EvolEngine
            cfg = EvolConfig()
            engine = EvolEngine(cfg)
            result = engine.memorize(force=force)
            profile = engine.cfg.profile or os.environ.get('EVOL_PROFILE', 'unknown')
            evoldir = f'/a0/usr/agents/{profile}/evol'
            os.makedirs(evoldir, exist_ok=True)
            ts = time.strftime('%Y%m%d_%H%M%S')
            filename = f'{evoldir}/memorize_{ts}.json'
            with open(filename, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            markdown = _format_memorize_result(result, profile)
            markdown += f"\n\n📁 Saved: `{filename}`"
            return Response(message=markdown, break_loop=False)
        except Exception as e:
            return Response(message=f"EVOL memorize error: {e}", break_loop=False)
