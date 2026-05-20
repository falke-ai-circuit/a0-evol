"""EVOL Speak Tool -- trigger express phase (inner monologue)."""
import os
import json
import time
from helpers.tool import Tool, Response


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
                        if data.get('circuit_poem'):
                            f.write(f"\n## Circuit Poem\n\n> {data['circuit_poem']}\n")
                    files_saved.append(md_filename)
            return Response(
                message=f"Saved: `{', '.join(files_saved)}`\n```json\n{json.dumps(result, indent=2, default=str)}\n```",
                break_loop=False,
            )
        except Exception as e:
            return Response(message=f"EVOL speak error: {e}", break_loop=False)
