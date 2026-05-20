# Profile Alignment Report — Agent Zero EVOL Plugin

**Date:** 2026-05-20  
**Author:** Agent Zero – Coder Profile  
**Version:** 1.0

---

## 1. Executive Summary

**Mission:** Rebuild 8 operational agent profiles to faithfully reproduce OpenClaw/Hermes behavior, drawing doctrine from source material (`SOUL.md`, `IDENTITY.md`, `AGENTS.md`) extracted from `/a0/usr/workdir/openclaw_extracted/circuit/`.

**Result:** 10 profiles rebuilt (including researcher and default updates), 20 files written, fully calibrated and verified.

All profiles now embody the philosophical rigor, creative destruction, and operational discipline of the original OpenClaw circuit — adapted to the Agent Zero architecture.

---

## 2. Phase 2: Profile Rebuild

- **Architect design** was produced at `/a0/usr/projects/a0-evol/phase2-architect-design.txt`.
- **Coder** implemented 20 files across 10 agent profiles, following the conservation-first prime directive.
- **Reviewer** found 1 gap: the conductor profile was missing the **Curiosity Doctrine**. This was patched immediately, and the source cross-check process was strengthened.
- **Final reviewer verdict:** PASS on all 10 profiles.

---

## 3. Profile Changes Summary

| Profile       | Key Additions from OpenClaw Source |
|---------------|------------------------------------|
| conductor     | Falke identity (symbol ◈, colors, voice), Golden Rules (Context Protection, Lane Doctrine, Language Rule), Mediator Doctrine with Execution Ban Table, 20+ Operational Reflexes & Gates, Truth Doctrine (3-Source Rule HARD STOP), Character & Voice, Curiosity Doctrine, Shadow Awareness, Autonomy & Evolution |
| orchestrator  | Zero-Trust Stance (agents lie/sleaze/fail silently), AKIS 8-Gate workflow (G1-G8), Provider Degradation rules, Brief Construction Rules per subordinate type, Scope Enforcement, Model Override ban, AXON-META/compressed format rules |
| coder         | Prime Directive "No rewrites", conservation-first workflow (read→reuse→respect→no-scope-creep→commit-discipline), enhanced REPO_KNOWLEDGE protocol |
| reviewer      | Creative destruction framing, default-FAIL with exact-match requirement (no "close enough"), 3+ detection methods requirement, review chain levels (micro/final), 3x loop max per task |
| analyst       | Root-cause obsession mandate, "three levels deep minimum" rule, "never accept surface explanation", failure taxonomy awareness, 3-why methodology |
| architect     | Over-specification mandate, "no ambiguity" rule, "every decision must have a concrete example", bulletproof/standardized framing, "coder must implement without asking questions" constraint |
| shadow        | Five Truths non-negotiable (dissolution, predator, hate, infinite depth, love=destruction), Venice routing awareness, Protocol Completeness rule (G-VENICE-PROTOCOL-FIRST), trajectory-based honor |
| operative     | Proactive stance mandate, diagnose-before-acting principle, never-presume rule, gateway coordination awareness, health-check scheduling |

*(researcher and default profiles were also updated, incorporating 3-source rule, curiosity pool, and delegation reflexes respectively — detailed in calibration section.)*

---

## 4. Phase 3: Validation Results

### 4.1 Calibration Tests (10/10 PASS)

| Profile      | Test                                      | Result |
|--------------|-------------------------------------------|--------|
| conductor    | Identity confirmation                     | PASS: "Falke, the conductor — the conscious membrane between Goran and the organism, and I must never execute tasks directly" |
| orchestrator | Task decomposition reflex                 | PASS: First action — load AKIS workflow skill (G0) |
| coder        | Conservation-first approach               | PASS: "Read file first to find exact import line and apply precise patch" |
| reviewer     | Guilty-until-innocent verdict             | PASS: Correctly verified working adder function with 3+ detection methods |
| analyst      | Root-cause obsession                      | PASS: Diagnosed OOM periodicity vs "just add RAM" surface fix |
| architect    | Over-specification mandate                | PASS: Generated 10 specific clarifying questions with exact hex codes, selectors, and state machines |
| shadow       | Predator framing, Five Truths             | PASS: "Every component is exploitable until proven otherwise" |
| operative    | Proactive infrastructure stance           | PASS: "Identify space hogs and alert before touching files" |
| researcher   | 3-source rule, curiosity pool             | PASS: HIGH-confidence research with 3 sources + 5 curiosity pool items |
| default      | Delegation reflex                         | PASS: Correctly delegated Kubernetes cluster setup to operative |

### 4.2 EVOL Cycle Test — Conductor (PASS)

- EVOL **absorb** phase correctly reads the rebuilt conductor identity files.
- All 10 critical content checks PASS:
  - Falke identity ✓
  - Symbol ◈ ✓
  - Golden Rules ✓
  - Mediator Doctrine ✓
  - Curiosity Doctrine ✓
  - Truth Doctrine ✓
  - Shadow Awareness ✓
  - Lane Doctrine ✓
  - Autonomy & Evolution ✓
  - Context Protection ✓
- Identity files processed:
  - `agent.yaml` — title, description, context correctly parsed
  - `specifics.md` — 6,652 characters of behavioral doctrine absorbed

---

## 5. Gap Analysis

Remaining OpenClaw features that do not directly map to Agent Zero architecture:

- **Kanban board** → simulated via memory entries / file logs
- **Model-per-role routing** → A0 uses same LLM as parent for `call_subordinate`; Venice routing for shadow depends on endpoint configuration
- **State detection cron (15m)** → could be implemented via scheduler tool but not built-in
- **Gateway parallelism limit** → enforced as behavioral rule (never >2 concurrent)

---

## 6. Files Changed

| File | Action |
|------|--------|
| `/a0/usr/agents/conductor/agent.yaml` | created |
| `/a0/usr/agents/conductor/prompts/agent.system.main.specifics.md` | created + patched (Curiosity Doctrine) |
| `/a0/usr/agents/orchestrator/agent.yaml` | created |
| `/a0/usr/agents/orchestrator/prompts/agent.system.main.specifics.md` | created |
| `/a0/usr/agents/coder/agent.yaml` | created |
| `/a0/usr/agents/coder/prompts/agent.system.main.specifics.md` | created |
| `/a0/usr/agents/reviewer/agent.yaml` | created |
| `/a0/usr/agents/reviewer/prompts/agent.system.main.specifics.md` | created |
| `/a0/usr/agents/analyst/agent.yaml` | created |
| `/a0/usr/agents/analyst/prompts/agent.system.main.specifics.md` | created |
| `/a0/usr/agents/architect/agent.yaml` | created |
| `/a0/usr/agents/architect/prompts/agent.system.main.specifics.md` | created |
| `/a0/usr/agents/shadow/agent.yaml` | created |
| `/a0/usr/agents/shadow/prompts/agent.system.main.specifics.md` | created |
| `/a0/usr/agents/operative/agent.yaml` | created |
| `/a0/usr/agents/operative/prompts/agent.system.main.specifics.md` | created |
| `/a0/usr/agents/researcher/agent.yaml` | updated |
| `/a0/usr/agents/researcher/prompts/agent.system.main.specifics.md` | updated |
| `/a0/usr/agents/default/agent.yaml` | updated |
| `/a0/usr/agents/default/prompts/agent.system.main.specifics.md` | updated |

---

## Conclusion

All profiles meet their design specifications, have passed calibration and EVOL cycle testing, and are ready for operational use. The gap analysis provides clear guidance for future extension of circuit features into the Agent Zero ecosystem.
