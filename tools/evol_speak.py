"""EVOL Speak Tool -- trigger express phase (inner monologue)."""
import os
import json
import time
from helpers.tool import Tool, Response


def _format_speak_result(result: dict, profile: str) -> str:
    lines = []
    lines.append(f"## 🗣️ EVOL Express — `{profile}`")
    lines.append("")
    status = result.get("status", "?")
    if status == "error":
        lines.append(f"**Error:** {result.get('error', 'unknown')}")
        return "\n".join(lines)
    if status == "skipped":
        lines.append(f"**Skipped:** {result.get('reason', 'unknown')}")
        return "\n".join(lines)
    data = result.get("data", {})
    mood = data.get("mood", "unknown")
    monologue = data.get("monologue", "")
    insights = data.get("insights", [])
    unanswered = data.get("unanswered", [])
    poem = data.get("identity_poem", "")
    portrait = data.get("portrait_prompt", "")
    lines.append(f"**Mood:** {mood}  |  **Insights:** {len(insights)}  |  **Unanswered:** {len(unanswered)}")
    lines.append("")
    if monologue:
        lines.append("### Inner Monologue")
        lines.append("")
        lines.append(f"> {monologue[:1000]}")
        lines.append("")
    if insights:
        lines.append("### Insights")
        for ins in insights[:5]:
            lines.append(f"- {str(ins)[:200]}")
        lines.append("")
    if unanswered:
        lines.append("### Unanswered Questions")
        for q in unanswered[:5]:
            lines.append(f"- {str(q)[:200]}")
        lines.append("")
    if poem:
        lines.append(f"> 🎶 *{poem[:300]}*")
        lines.append("")
    if portrait:
        lines.append(f"**Portrait prompt:** {portrait[:200]}")
        lines.append("")
    return "\n".join(lines)


class EvolSpeakTool(Tool):
    async def execute(self, force: bool = False, **kwargs) -> Response:
        try:
            from usr.plugins.a0_evol.helpers.config import EvolConfig
            from usr.plugins.a0_evol.helpers.engine import EvolEngine
            cfg = EvolConfig()
            engine = EvolEngine(cfg)
            result = engine.speak(force=force)
            profile = engine.cfg.profile or os.environ.get('EVOL_PROFILE', 'unknown')
            evoldir = f'/a0/usr/agents/{profile}/evol'
            os.makedirs(evoldir, exist_ok=True)
            ts = time.strftime('%Y%m%d_%H%M%S')
            # Save full result as JSON
            json_filename = f'{evoldir}/speak_{ts}.json'
            with open(json_filename, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            # Save monologue separately as markdown if available
            files_saved = [json_filename]
            if result.get('status') == 'ok' and result.get('data'):
                data = result['data']
                monologue = data.get('monologue', '')
                if monologue:
                    md_filename = f'{evoldir}/monologue_{ts}.md'
                    with open(md_filename, 'w') as f:
                        f.write(f"# Monologue \u2014 {ts}\n\n")
                        f.write(f"**Mood:** {data.get('mood', 'unknown')}\n\n")
                        f.write(f"---\n\n{monologue}\n\n---\n\n")
                        if data.get('insights'):
                            f.write(f"## Insights\n\n")
                            for ins in data['insights']:
                                f.write(f"- {ins}\n")
                        if data.get('unanswered'):
                            f.write(f"\n## Unanswered\n\n")
                            for q in data['unanswered']:
                                f.write(f"- {q}\n")
                        if data.get('identity_poem'):
                            f.write(f"\n## Identity Poem\n\n> {data['identity_poem']}\n")
                    files_saved.append(md_filename)
            markdown = _format_speak_result(result, profile)
            markdown += f"\n\n📁 Saved: `{', '.join(files_saved)}`"
            return Response(message=markdown, break_loop=False)
        except Exception as e:
            return Response(message=f"EVOL speak error: {e}", break_loop=False)
