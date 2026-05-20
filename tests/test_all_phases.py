#!/usr/bin/env python3
"""
Comprehensive EVOL phase test across all 11 agent profiles.

Tests: absorb → reflect → explore → express → memorize
For each profile, an EvolConfig is created with edit_mode='readonly'
and each phase is called directly, capturing outputs and exceptions.
"""

import sys
import os

# Ensure project helpers are importable
PROJECT_ROOT = "/a0/usr/projects/a0-evol"
sys.path.insert(0, PROJECT_ROOT)

# Also ensure the usr plugins path exists for internal import attempts
sys.path.insert(0, "/a0/usr")

from helpers.config import EvolConfig
from helpers.registry import (
    absorb, reflect, explore, express, memorize
)

# ── All profiles to test ──
PROFILES = [
    "agent0",
    "analyst",
    "architect",
    "coder",
    "conductor",
    "default",
    "operative",
    "orchestrator",
    "researcher",
    "reviewer",
    "shadow",
]

# ── Helper: detect fallback for a phase result ──
def is_reflect_fallback(reflected):
    """Reflect fallback: first pattern contains 'Reflect failed:'"""
    patterns = reflected.get("patterns", [])
    return len(patterns) == 1 and patterns[0].startswith("Reflect failed:")

def is_explore_fallback(explored, reflected):
    """Explore fallback: queries == patterns (LLM failed) or no discoveries"""
    # If LLM failed, queries will be patterns directly, not synthesized queries
    # Also, discoveries will be empty or from raw results
    # A simple heuristic: if discoveries list length == 0 and queries list length > 0 but queries are just the pattern strings (not search-like keywords) => fallback
    # Actually after fallback, explore returns `queries` that were the patterns themselves, and `results` from search backends.
    # We can check if the `discoveries` list is empty (or only contains simple title/snippet from raw results) and if `queries` are not really keyword queries (they are the full pattern strings).
    # For simplicity: if `discoveries` list is empty -> fallback likely used.
    discoveries = explored.get("discoveries", [])
    if not discoveries:
        return True
    # Check if discoveries are just raw results (no novelty synthesized) — but that's ok.
    # A better indicator: if `queries` contains one of the reflected patterns verbatim (since LLM failed).
    queries = explored.get("queries", [])
    patterns = reflected.get("patterns", []) + reflected.get("anomalies", [])
    for q in queries:
        if q in patterns:
            return True
    return False

def is_express_fallback(expressed):
    """Express fallback: monologue starts with 'Express failed:'"""
    monologue = expressed.get("monologue", "")
    return monologue.startswith("Express failed:")

def is_memorize_fallback(memorized):
    """Memorize fallback: fallback_used key is True"""
    return memorized.get("fallback_used", False)

# ── Runner ──
def test_profile(profile_name):
    """Run all phases for a single profile and return structured results."""
    print(f"\n{'='*60}")
    print(f"  Testing profile: {profile_name}")
    print(f"{'='*60}")

    results = {
        "profile": profile_name,
        "phases": {},
        "errors": []
    }

    # ── Config ──
    try:
        cfg = EvolConfig(profile=profile_name, mode="profile")
        cfg.edit_mode = "readonly"  # No writes
    except Exception as e:
        results["errors"].append(f"Config creation failed: {e}")
        return results

    # ── Phase 1: Absorb ──
    print(f"  [absorb] running...")
    try:
        absorbed = absorb(cfg)
        sources_count = len(absorbed.get("identity_files", {}))
        results["phases"]["absorb"] = {
            "status": "OK",
            "sources_count": sources_count,
            "idle_depth": absorbed.get("idle_depth", "?"),
        }
        print(f"           status=OK | sources_count={sources_count}")
    except Exception as e:
        results["phases"]["absorb"] = {"status": "FAIL", "error": str(e)[:200]}
        results["errors"].append(f"absorb: {e}")
        print(f"           status=FAIL | error={str(e)[:100]}")
        absorbed = {"identity_files": {}, "session_summary": "", "evolution_log": []}

    # ── Phase 2: Reflect ──
    print(f"  [reflect] running...")
    reflected = {}
    try:
        reflected = reflect(cfg, absorbed)
        patterns_n = len(reflected.get("patterns", []))
        anomalies_n = len(reflected.get("anomalies", []))
        bridge_n = len(reflected.get("bridge_signals", []))
        fallback = is_reflect_fallback(reflected)
        results["phases"]["reflect"] = {
            "status": "OK",
            "patterns": patterns_n,
            "anomalies": anomalies_n,
            "bridge_signals": bridge_n,
            "fallback_used": fallback,
        }
        print(f"           status=OK | patterns={patterns_n} anomalies={anomalies_n} bridge_signals={bridge_n} | fallback={fallback}")
    except Exception as e:
        results["phases"]["reflect"] = {"status": "FAIL", "error": str(e)[:200]}
        results["errors"].append(f"reflect: {e}")
        print(f"           status=FAIL | error={str(e)[:100]}")
        reflected = {"patterns": [], "anomalies": [], "bridge_signals": []}

    # ── Phase 3: Explore ──
    print(f"  [explore] running...")
    explored = {}
    try:
        explored = explore(cfg, reflected)
        queries_n = len(explored.get("queries", []))
        discoveries_n = len(explored.get("discoveries", []))
        fallback = is_explore_fallback(explored, reflected)
        results["phases"]["explore"] = {
            "status": "OK",
            "queries": queries_n,
            "discoveries": discoveries_n,
            "fallback_used": fallback,
        }
        print(f"           status=OK | queries={queries_n} discoveries={discoveries_n} | fallback={fallback}")
    except Exception as e:
        results["phases"]["explore"] = {"status": "FAIL", "error": str(e)[:200]}
        results["errors"].append(f"explore: {e}")
        print(f"           status=FAIL | error={str(e)[:100]}")
        explored = {"queries": [], "results": [], "discoveries": []}

    # ── Phase 4: Express ──
    print(f"  [express] running...")
    expressed = {}
    try:
        expressed = express(cfg, reflected, explored)
        insights_n = len(expressed.get("insights", []))
        mood = expressed.get("mood", "?")
        monologue_len = len(expressed.get("monologue", ""))
        fallback = is_express_fallback(expressed)
        results["phases"]["express"] = {
            "status": "OK",
            "insights": insights_n,
            "mood": mood,
            "monologue_len": monologue_len,
            "fallback_used": fallback,
        }
        print(f"           status=OK | insights={insights_n} mood='{mood}' monologue_len={monologue_len} | fallback={fallback}")
    except Exception as e:
        results["phases"]["express"] = {"status": "FAIL", "error": str(e)[:200]}
        results["errors"].append(f"express: {e}")
        print(f"           status=FAIL | error={str(e)[:100]}")
        expressed = {}

    # ── Phase 5: Memorize ──
    print(f"  [memorize] running...")
    memorized = {}
    try:
        memorized = memorize(cfg, reflected, expressed, explored)
        items_scored = len(memorized.get("items", []))
        applied_n = len(memorized.get("applied", []))
        proposed_n = len(memorized.get("proposals", []))
        fallback = is_memorize_fallback(memorized)
        results["phases"]["memorize"] = {
            "status": "OK",
            "items_scored": items_scored,
            "applied": applied_n,
            "proposed": proposed_n,
            "fallback_used": fallback,
        }
        print(f"           status=OK | items_scored={items_scored} applied={applied_n} proposed={proposed_n} | fallback={fallback}")
    except Exception as e:
        results["phases"]["memorize"] = {"status": "FAIL", "error": str(e)[:200]}
        results["errors"].append(f"memorize: {e}")
        print(f"           status=FAIL | error={str(e)[:100]}")

    return results


# ── Summary table printer ──
def print_summary(all_results):
    print(f"\n\n{'='*120}")
    print(f"  COMPREHENSIVE EVOL PHASE TEST SUMMARY")
    print(f"{'='*120}")
    # Header
    print(f"{'Profile':<16} {'absorb':>8} {'reflect':>10} {'explore':>9} {'express':>8} {'memorize':>10}  {'Fallback'}")
    print(f"{'-'*16} {'-'*8} {'-'*10} {'-'*9} {'-'*8} {'-'*10}  {'-'*20}")

    for res in all_results:
        profile = res["profile"]
        phases = res["phases"]
        errors = res.get("errors", [])

        def phase_status(phase_name):
            p = phases.get(phase_name, {})
            return p.get("status", "N/A")

        absorb_str = phase_status("absorb")
        reflect_str = phase_status("reflect")
        explore_str = phase_status("explore")
        express_str = phase_status("express")
        memor_str = phase_status("memorize")

        # Collect fallback info
        fb_parts = []
        if phases.get("reflect", {}).get("fallback_used"):
            fb_parts.append("R")
        if phases.get("explore", {}).get("fallback_used"):
            fb_parts.append("Ex")
        if phases.get("express", {}).get("fallback_used"):
            fb_parts.append("Ep")
        if phases.get("memorize", {}).get("fallback_used"):
            fb_parts.append("M")
        fallback_str = ",".join(fb_parts) if fb_parts else "-"
        if errors:
            fallback_str += " [ERR]"

        print(f"{profile:<16} {absorb_str:>8} {reflect_str:>10} {explore_str:>9} {express_str:>8} {memor_str:>10}  {fallback_str}")

    print(f"{'='*120}")

    # Per-profile details
    print(f"\nDetailed per-phase metrics:\n")
    for res in all_results:
        profile = res["profile"]
        print(f"  [{profile}]")
        for phase in ["absorb", "reflect", "explore", "express", "memorize"]:
            pdata = res["phases"].get(phase, {})
            print(f"    {phase}: {pdata}")
        if res.get("errors"):
            print(f"    errors: {res['errors']}")
        print()


# ── Main ──
def main():
    all_results = []
    for profile in PROFILES:
        result = test_profile(profile)
        all_results.append(result)

    print_summary(all_results)

    # Determine overall pass/fail (all phases OK for all profiles)
    all_ok = True
    for res in all_results:
        for phase in ["absorb", "reflect", "explore", "express", "memorize"]:
            if res["phases"].get(phase, {}).get("status") != "OK":
                all_ok = False
                break
    print(f"\nOverall: {'SUCCESS' if all_ok else 'FAILURE (some phases failed)'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
