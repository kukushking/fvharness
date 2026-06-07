"""MutationHarness — the local reward signal.

The contest scores specs by mutation testing, but Certora's official mutation report is
dashboard-only (no documented machine-readable export). So we run our *own* mutation loop to
get a programmatic coverage score the agent loop can optimize against:

    for each mutant:  run the spec on a copy of the contest with that mutant patched in
    caught   = a rule that was VERIFIED on the original is now VIOLATED  (good — bug detected)
    survived = the mutant passes the spec unchanged                      (gap — feed it back)

    coverage = caught / total

Mutants come from two sources:
  1. Provided public mutants in the contest's `mutations/` dir (the real public set).
  2. A built-in mutator that injects common bug classes into the target contract, so the
     loop has a signal even before/without the cloud mutator.

Honest caveat: our self-generated mutants are a *proxy* for the judges' private mutants.
Broad invariants that kill ours should generalize, but coverage here ≠ contest coverage.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from fvharness.certora import CertoraVerifier, RuleStatus, VerificationResult


@dataclass
class Mutant:
    name: str                 # human label, e.g. "require-removal@Vault.sol:142"
    rel_path: str             # contract file (relative to contest dir) the mutation hits
    mutated_source: str       # full mutated file contents
    description: str          # what bug was injected (fed to the model when it survives)


@dataclass
class CoverageReport:
    total: int
    caught: list[Mutant] = field(default_factory=list)
    survived: list[Mutant] = field(default_factory=list)

    @property
    def score(self) -> float:
        return len(self.caught) / self.total if self.total else 0.0

    def feedback(self) -> str:
        """Surviving mutants, formatted for the model to widen coverage."""
        if not self.survived:
            return "All mutants caught."
        lines = [f"{len(self.survived)}/{self.total} mutants SURVIVED (not caught). "
                 f"Add/strengthen properties to catch these injected bugs:"]
        for m in self.survived:
            lines.append(f"  - {m.name}: {m.description}")
        return "\n".join(lines)


# --- built-in mutator: common Solidity bug classes -------------------------------------
# Each (pattern, replacement, label) flips one operator/guard. Conservative on purpose —
# we want mutants that are plausible bugs, not syntax errors. Applied one at a time.
_MUTATIONS: list[tuple[str, str, str]] = [
    (r"\brequire\s*\([^;]*\);", "", "require-removal"),          # drop a precondition guard
    (r">=", ">", "ge->gt (off-by-one)"),
    (r"<=", "<", "le->lt (off-by-one)"),
    (r"(?<![<>=!])==", "!=", "eq->neq"),
    (r"\+=", "-=", "plus->minus assign"),
    (r"(?<![+\-*/])\+(?![+=])", "-", "plus->minus"),
]


class MutationHarness:
    def __init__(self, contest_dir: Path, verifier: CertoraVerifier) -> None:
        self.contest_dir = Path(contest_dir).resolve()
        self.verifier = verifier

    # --- mutant generation ---------------------------------------------------------------
    def load_public_mutants(self, mutations_subdir: str = "certora/mutations") -> list[Mutant]:
        """Load provided public mutants. Layout varies per contest; this handles the common
        case of `<mutations>/<Contract>/<n>.sol` being a full mutated file."""
        root = self.contest_dir / mutations_subdir
        out: list[Mutant] = []
        if not root.exists():
            return out
        for sol in sorted(root.rglob("*.sol")):
            # Heuristic: a public mutant named <Contract>/<k>.sol maps back to a contract
            # file of the same stem somewhere under the contest. Resolve on use; store name.
            out.append(Mutant(
                name=f"public:{sol.relative_to(root)}",
                rel_path=self._guess_target(sol.stem),
                mutated_source=sol.read_text(encoding="utf-8"),
                description=f"provided public mutant {sol.relative_to(root)}",
            ))
        return out

    def generate(self, target_rel: str, max_mutants: int = 12) -> list[Mutant]:
        """Inject built-in bug classes into one contract file, one mutation per mutant."""
        src_path = self.contest_dir / target_rel
        source = src_path.read_text(encoding="utf-8")
        mutants: list[Mutant] = []
        for pattern, repl, label in _MUTATIONS:
            for m in re.finditer(pattern, source):
                mutated = source[:m.start()] + repl + source[m.end():]
                if mutated == source:
                    continue
                line = source[:m.start()].count("\n") + 1
                mutants.append(Mutant(
                    name=f"{label}@{target_rel}:{line}",
                    rel_path=target_rel,
                    mutated_source=mutated,
                    description=f"{label} at {target_rel} line {line} "
                                f"(changed `{m.group(0)[:40]}`)",
                ))
                if len(mutants) >= max_mutants:
                    return mutants
        return mutants

    def _guess_target(self, stem: str) -> str:
        for sol in self.contest_dir.rglob(f"{stem}.sol"):
            if "mutations" not in sol.parts:
                return str(sol.relative_to(self.contest_dir))
        return f"{stem}.sol"

    # --- scoring -------------------------------------------------------------------------
    def score(self, conf: str, baseline: VerificationResult,
              mutants: list[Mutant]) -> CoverageReport:
        """Run the (already-on-original-passing) spec against each mutant.

        `baseline` is the result of verifying the current spec on the ORIGINAL contract — we
        only count a flip on rules that were VERIFIED there, so a rule that was already noisy
        doesn't get false credit.
        """
        baseline_verified = {r for r, s in baseline.rules.items() if s is RuleStatus.VERIFIED}
        report = CoverageReport(total=len(mutants))
        for mut in mutants:
            if self._mutant_caught(conf, mut, baseline_verified):
                report.caught.append(mut)
            else:
                report.survived.append(mut)
        return report

    def _mutant_caught(self, conf: str, mut: Mutant, baseline_verified: set[str]) -> bool:
        """Patch the mutant into a temp copy of the contest and re-run the Prover there."""
        with tempfile.TemporaryDirectory(prefix="fvmut-") as tmp:
            tmp_dir = Path(tmp) / "contest"
            shutil.copytree(self.contest_dir, tmp_dir, dirs_exist_ok=True)
            (tmp_dir / mut.rel_path).write_text(mut.mutated_source, encoding="utf-8")
            res = self.verifier.verify(conf, cwd=tmp_dir)
            # No per-rule data parsed yet? Fall back to overall ok: a correct spec FAILS on a
            # real bug, so `not res.ok` == caught. Once the parser is calibrated, prefer the
            # precise rule-flip check below (avoids crediting unrelated errors as catches).
            if not res.rules:
                return not res.ok
            if baseline_verified:
                return any(res.rules.get(r) is RuleStatus.VIOLATED for r in baseline_verified)
            return bool(res.violated())
