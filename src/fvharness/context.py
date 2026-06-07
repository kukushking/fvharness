"""Build the prompt context handed to the prover: the contract source the spec must verify,
plus contest scope notes and the current spec (when repairing).

Lesson carried from ../theorem/_erdos/runner.py: feed the model the *full upstream
definitions*, not just a signature. Here that means the actual Solidity it's writing
properties about — the model can't write a sound invariant about `totalSupply` without
seeing how the contract maintains it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_MAX_SOURCE_CHARS = 120_000  # keep well within context; trim with a note if a contract is huge


def load_conf(contest_dir: Path, conf_rel: str) -> dict:
    """Parse a .conf (JSON5-ish; we tolerate // comments and trailing commas)."""
    text = (contest_dir / conf_rel).read_text(encoding="utf-8")
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def _conf_contract_files(contest_dir: Path, conf: dict) -> list[Path]:
    files = conf.get("files", [])
    out: list[Path] = []
    for f in files:
        # entries look like "contracts/Vault.sol" or "contracts/Vault.sol:Vault"
        rel = f.split(":")[0]
        p = contest_dir / rel
        if p.exists():
            out.append(p)
    return out


def build_context(contest_dir: Path, conf_rel: str, current_spec: str | None = None) -> str:
    """Assemble: scope notes + the contracts under verification + the current spec."""
    contest_dir = Path(contest_dir).resolve()
    conf = load_conf(contest_dir, conf_rel)
    parts: list[str] = []

    # Scope / instructions, if the contest ships a README.
    for readme in ("README.md", "README", "SCOPE.md"):
        rp = contest_dir / readme
        if rp.exists():
            parts.append(f"# Contest scope ({readme})\n{rp.read_text(encoding='utf-8')[:8000]}")
            break

    parts.append(f"# Verification config ({conf_rel})\n```json\n"
                 f"{json.dumps(conf, indent=2)}\n```")

    # The actual contracts the spec must verify.
    budget = _MAX_SOURCE_CHARS
    parts.append("# Contracts under verification")
    for p in _conf_contract_files(contest_dir, conf):
        src = p.read_text(encoding="utf-8")
        rel = p.relative_to(contest_dir)
        if len(src) > budget:
            src = src[:budget] + f"\n// … [truncated — {rel} exceeds context budget]"
        budget -= len(src)
        parts.append(f"## {rel}\n```solidity\n{src}\n```")
        if budget <= 0:
            parts.append("// … [further contracts omitted — context budget exhausted]")
            break

    if current_spec:
        parts.append(f"# Current spec (improve it)\n```cvl\n{current_spec}\n```")
    else:
        parts.append("# Task\nWrite the initial .spec. Start with broad, high-level "
                     "invariants about the protocol's core safety properties, then add "
                     "parametric rules. Ensure everything verifies on this (correct) code.")
    return "\n\n".join(parts)


def load_cvl_reference(repo_root: Path) -> str:
    ref = repo_root / "cvl_reference" / "CHEATSHEET.md"
    return ref.read_text(encoding="utf-8") if ref.exists() else ""
