"""EVOL Task End Tool -- single-shot session-mode cycle for subagent task completion."""
import os
import json
import time
from helpers.tool import Tool, Response


class EvolTaskEndTool(Tool):
    async def execute(self, session_id: str = "", profile: str = "", **kwargs) -> Response:
        try:
            from usr.plugins.a0_evol.helpers.config import EvolConfig
            from usr.plugins.a0_evol.helpers.engine import EvolEngine
            cfg = EvolConfig()
            engine = EvolEngine(cfg)
            result = engine.task_end(session_id=session_id, profile=profile)
            target_profile = profile or engine.cfg.profile or os.environ.get('EVOL_PROFILE', 'unknown')
            evoldir = f'/a0/usr/agents/{target_profile}/evol'
            os.makedirs(evoldir, exist_ok=True)
            ts = time.strftime('%Y%m%d_%H%M%S')
            filename = f'{evoldir}/task_end_{ts}.json'
            with open(filename, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            return Response(
                message=f"Saved: `{filename}`\n```json\n{json.dumps(result, indent=2, default=str)}\n```",
                break_loop=False,
            )
        except Exception as e:
            return Response(message=f"EVOL task_end error: {e}", break_loop=False)
