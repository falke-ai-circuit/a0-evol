"""EVOL Explore Tool -- trigger explore phase (curiosity + research)."""
import os
import json
import time
from helpers.tool import Tool, Response


def _format_explore_result(result: dict, profile: str) -> str:
    lines = []
    lines.append(f"## 🌐 EVOL Explore — `{profile}`")
    lines.append("")
    status = result.get("status", "?")
    if status == "error":
        lines.append(f"**Error:** {result.get('error', 'unknown')}")
        return "\n".join(lines)
    if status == "skipped":
        lines.append(f"**Skipped:** {result.get('reason', 'unknown')}")
        return "\n".join(lines)
    data = result.get("data", {})
    queries = data.get("queries", [])
    results = data.get("results", [])
    discoveries = data.get("discoveries", [])
    lines.append(f"**Queries:** {len(queries)}  |  **Results:** {len(results)}  |  **Discoveries:** {len(discoveries)}")
    lines.append("")
    if queries:
        lines.append("### Queries Submitted")
        for q in queries[:5]:
            lines.append(f"- {str(q)[:300]}")
        lines.append("")
    if results:
        lines.append("### Search Results")
        for r in results[:5]:
            lines.append(f"- {str(r)[:300]}")
        lines.append("")
    if discoveries:
        lines.append("### Discoveries")
        for d in discoveries[:5]:
            if isinstance(d, dict):
                title = d.get("title", "")
                novelty = d.get("novelty", 0)
                lines.append(f"- `{novelty:.2f}` — {title[:250]}")
            else:
                lines.append(f"- {str(d)[:250]}")
        lines.append("")
    return "\n".join(lines)


class EvolExploreTool(Tool):
    async def execute(self, force: bool = False, **kwargs) -> Response:
        try:
            from usr.plugins.a0_evol.helpers.config import EvolConfig
            from usr.plugins.a0_evol.helpers.engine import EvolEngine
            cfg = EvolConfig()
            engine = EvolEngine(cfg)
            result = engine.explore(force=force)
            profile = engine.cfg.profile or os.environ.get('EVOL_PROFILE', 'unknown')
            evoldir = f'/a0/usr/agents/{profile}/evol'
            os.makedirs(evoldir, exist_ok=True)
            ts = time.strftime('%Y%m%d_%H%M%S')
            filename = f'{evoldir}/explore_{ts}.json'
            with open(filename, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            markdown = _format_explore_result(result, profile)
            markdown += f"\n\n📁 Saved: `{filename}`"
            return Response(message=markdown, break_loop=False)
        except Exception as e:
            return Response(message=f"EVOL explore error: {e}", break_loop=False)
