"""CvlProver — Claude Opus writes and repairs CVL specifications.

Mirrors the Prover abstraction in ../theorem (propose given context + prior failures), but
emits CVL instead of Lean. Uses Claude Opus 4.8 with adaptive thinking + high effort
(spec-writing is intelligence-sensitive), and streams (specs + thinking can be long).
"""
from __future__ import annotations

import os
import re
from typing import Protocol

import anthropic

MODEL = "claude-opus-4-8"
MAX_TOKENS = 32000

# The system prompt encodes the contest's scoring strategy (see PLAYBOOK.md). It's stable
# across the whole run, so we cache it. The CVL reference is appended here as grounding —
# improving it is a tuning lever, exactly like the "write Lean 4 not Lean 3" clause that was
# load-bearing in ../theorem/04-llm-agent/MY_RESULTS.md.
_SYSTEM = """\
You are an expert in formal verification with the Certora Prover, writing CVL \
(Certora Verification Language) specifications to compete in a Certora FV contest.

How you are scored — internalize this, it dictates strategy:
- Specs are graded by MUTATION TESTING. The judges inject bugs (mutants) into the contract \
and check whether your rules CATCH them (a rule flips to VIOLATED on the buggy code while \
staying VERIFIED on the correct code).
- TWO HARD CONSTRAINTS, in order:
  1. Every rule/invariant MUST pass (VERIFIED) on the ORIGINAL, correct contract. A rule that \
reports a counterexample on correct code is a false positive and is worthless — fix it first.
  2. Subject to (1), rules must CATCH as many mutants as possible.
- BROAD, HIGH-LEVEL properties beat many narrow rules. One strong invariant about a core \
protocol property (conservation of funds, solvency, access control, monotonicity, \
correct accounting) often catches many mutants at once. Maximize coverage breadth.
- Rare catches pay the most, so after the obvious properties, reach for deep/unusual \
invariants others would miss.

Write idiomatic CVL: `methods { ... }` blocks (declare env-free/`envfree` where valid), \
`rule`s with `env e` / `calldataarg args`, `invariant`s, `require`/`assert`, ghost variables \
and `hook`s for tracking state, and parametric rules over `method f`. Prefer invariants and \
parametric rules for breadth. Keep it compiling — if unsure of an exact lemma/signature, \
choose the form most likely to verify and stay sound. Consult Certora docs conventions; do \
NOT invent Solidity-looking syntax that isn't valid CVL.

Output ONLY the complete `.spec` file contents, in a single ```cvl code block. No prose \
outside the block.
"""


class Prover(Protocol):
    def propose(self, context: str, prior_failures: list[str]) -> str: ...


class CvlProver:
    def __init__(self, model: str = MODEL, cvl_reference: str = "") -> None:
        self.model = model
        # Claude Code force-scrubs ANTHROPIC_API_KEY from tool subprocesses (even values set
        # in ~/.zshenv), but leaves custom var names alone. So accept FVHARNESS_ANTHROPIC_KEY
        # as an escape hatch when running inside Claude Code, and fall back to the SDK's
        # normal ANTHROPIC_API_KEY resolution when run from a regular terminal.
        key = os.environ.get("FVHARNESS_ANTHROPIC_KEY")
        self.client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        self.system = _SYSTEM
        if cvl_reference.strip():
            self.system += "\n\n# CVL reference (grounding)\n" + cvl_reference.strip()

    def propose(self, context: str, prior_failures: list[str]) -> str:
        user = context
        if prior_failures:
            user += "\n\n# Feedback from previous attempts (fix these)\n"
            # Only the most recent few matter; older ones are usually superseded.
            for i, f in enumerate(prior_failures[-3:], 1):
                user += f"\n## Attempt feedback {i}\n{f}\n"
            user += ("\nReturn a corrected, complete .spec. Keep rules that already verified "
                     "and pass on the original; repair false positives; add properties to "
                     "catch the surviving mutants.")

        with self.client.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=[{"type": "text", "text": self.system,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        ) as stream:
            msg = stream.get_final_message()

        text = next((b.text for b in msg.content if b.type == "text"), "")
        return _extract_spec(text)


_FENCE = re.compile(r"```(?:cvl|spec|solidity)?\s*\n(.*?)```", re.DOTALL)


def _extract_spec(text: str) -> str:
    """Pull the .spec body out of the model's fenced block; fall back to raw text."""
    m = _FENCE.search(text)
    return (m.group(1) if m else text).strip() + "\n"
