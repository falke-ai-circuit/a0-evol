"""EVOL Memorize Tool -- trigger memorize phase (memory consolidation)."""
import os
import json
import time
from helpers.tool import Tool, Response


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
            return Response(
                message=f"Saved: `{filename}`\n```json\n{json.dumps(result, indent=2, default=str)}\n```",
                break_loop=False,
            )
        except Exception as e:
            return Response(message=f"EVOL memorize error: {e}", break_loop=False)
