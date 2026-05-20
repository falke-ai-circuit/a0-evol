# AKIS 8-Gate Workflow — a0-evol Project

> All code changes in this project must follow this workflow.
> No agent may write code directly — the orchestrator owns all implementation.

## Gates

| Gate | Name | Action |
|------|------|--------|
| G1 | Knowledge Query | Read project_knowledge.json for gotchas, recent changes |
| G2 | Structured Plan | Create a TODO with clear steps |
| G3 | Skill Preload | Load relevant skills (evol, plugin-dev) |
| G4 | Intent Announce | Announce what and why to the user |
| G5 | Execute + Verify | Implement via orchestrator→coder+reviewer pipeline |
| G6 | Workflow Log | Append to .github/workflow-log.jsonl |
| G7 | Knowledge Update | Run python .github/scripts/knowledge.py --update |

## Anti-Patterns
- ❌ Skip G1 → repeat known mistakes
- ❌ Edit without G3 → miss format rules
- ❌ Commit without G6 → no audit trail
- ❌ Skip G7 → stale knowledge base
- ❌ Write code directly (always use orchestrator)
