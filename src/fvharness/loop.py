"""The agent loop: propose CVL → verify on original → score vs mutants → feed back → iterate.

    uv run fvharness --contest contests/silo-v2 --conf certora/confs/Silo.conf

Mirrors ../theorem/04-llm-agent/agent.py, with the Certora Prover as the verifier and a
mutation-coverage score as the optimization target. The two scoring constraints (no false
positives on the original, then catch mutants) are enforced in that order.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from fvharness.certora import CertoraVerifier
from fvharness.context import build_context, load_conf, load_cvl_reference
from fvharness.mutation import MutationHarness
from fvharness.prover import CvlProver

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _spec_path_from_conf(conf: dict) -> str | None:
    """conf['verify'] looks like 'Contract:certora/specs/Foo.spec' — pull the spec path."""
    verify = conf.get("verify")
    if isinstance(verify, str) and ":" in verify:
        return verify.split(":", 1)[1]
    return None


def _first_contract(conf: dict) -> str | None:
    files = conf.get("files", [])
    return files[0].split(":")[0] if files else None


def run(contest_dir: Path, conf_rel: str, spec_rel: str | None, target_rel: str | None,
        max_iters: int, coverage_target: float, calibrate: bool, max_mutants: int = 12) -> int:
    contest_dir = Path(contest_dir).resolve()
    conf = load_conf(contest_dir, conf_rel)

    spec_rel = spec_rel or _spec_path_from_conf(conf)
    if not spec_rel:
        sys.exit("Could not determine the .spec output path. Pass --spec <path-in-contest>.")
    spec_path = contest_dir / spec_rel
    spec_path.parent.mkdir(parents=True, exist_ok=True)

    target_rel = target_rel or _first_contract(conf)

    verifier = CertoraVerifier(contest_dir, calibrate=calibrate)
    prover = CvlProver(cvl_reference=load_cvl_reference(_REPO_ROOT))
    mutator = MutationHarness(contest_dir, verifier)

    # Assemble the mutant set once: provided public mutants + our injected ones.
    mutants = mutator.load_public_mutants()
    if target_rel:
        mutants += mutator.generate(target_rel, max_mutants=max_mutants)
    print(f"[setup] {len(mutants)} mutants "
          f"(target contract: {target_rel}); spec → {spec_rel}")

    best_spec, best_score = None, -1.0
    prior_failures: list[str] = []
    current_spec: str | None = None

    for n in range(1, max_iters + 1):
        print(f"\n=== iteration {n}/{max_iters} ===")
        context = build_context(contest_dir, conf_rel, current_spec)
        spec = prover.propose(context, prior_failures)
        spec_path.write_text(spec, encoding="utf-8")
        current_spec = spec
        print(f"  proposed spec: {len(spec)} chars → {spec_rel}")

        # Constraint 1: must pass on the ORIGINAL contract.
        base = verifier.verify(conf_rel)
        if base.report_url:
            print(f"  prover: {base.report_url}")
        if not base.ok:
            fps = base.violated()
            print(f"  ✗ false positives / errors on original: {base.short()}")
            if fps:
                # Specific, surgical feedback: name the exact offending rules and tell the
                # model to fix/remove ONLY those, keeping everything that verified.
                fb = (
                    f"The spec did NOT verify on the ORIGINAL (correct) contract. These rules "
                    f"reported a counterexample on correct code — they are FALSE POSITIVES "
                    f"(either logically wrong or too strong):\n"
                    f"    {', '.join(fps)}\n"
                    f"Fix or remove ONLY these rules. Keep every other rule unchanged — they "
                    f"verified. A false positive usually means the rule asserts something the "
                    f"contract doesn't actually guarantee, or a method-classification "
                    f"`definition` is missing a case (a method that legitimately changes the "
                    f"quantity isn't listed). Inspect the counterexample below and the "
                    f"contract source, then correct the classification or weaken the assertion.\n"
                    f"\nProver output (tail):\n{base.raw[-2500:]}")
            else:
                # No rule parsed → likely a CVL compile/typecheck error (now caught locally).
                fb = (
                    f"The spec FAILED to compile or typecheck against the contract. Fix the CVL "
                    f"errors below — common causes: a storage hook referencing a field name "
                    f"that doesn't exist in this contract, a wrong method signature in the "
                    f"`methods` block, or invalid CVL syntax.\n"
                    f"\nProver output (tail):\n{base.raw[-3000:]}")
            prior_failures.append(fb)
            continue
        print(f"  ✓ verifies on original: {base.short()}")

        # Constraint 2: catch mutants.
        report = mutator.score(conf_rel, base, mutants)
        print(f"  coverage: {len(report.caught)}/{report.total} mutants caught "
              f"(score={report.score:.2f})")
        if report.score > best_score:
            best_score, best_spec = report.score, spec

        if report.score >= coverage_target:
            print(f"  ✓ hit coverage target {coverage_target:.0%}")
            break
        prior_failures.append(report.feedback())

    if best_spec is not None:
        spec_path.write_text(best_spec, encoding="utf-8")
    print(f"\n=== done === best coverage {max(best_score, 0):.0%}; "
          f"best spec written to {spec_rel}")
    print("Submit by pushing your contest repo (with this spec) and adding the judges as "
          "collaborators. Coverage here is a PROXY for the judges' private mutants — review "
          "the spec for deeper protocol invariants before submitting.")
    return 0 if best_score >= 0 else 1


def main() -> None:
    p = argparse.ArgumentParser(description="Certora FV contest harness (LLM writes CVL).")
    p.add_argument("--contest", required=True, help="path to the cloned contest dir")
    p.add_argument("--conf", required=True, help="path to the .conf, relative to --contest")
    p.add_argument("--spec", default=None,
                   help="where to write the .spec (relative to --contest); "
                        "defaults to the path in conf['verify']")
    p.add_argument("--target", default=None,
                   help="contract file to mutate (relative to --contest); "
                        "defaults to conf['files'][0]")
    p.add_argument("--max-iters", type=int, default=6)
    p.add_argument("--max-mutants", type=int, default=12,
                   help="cap on built-in mutants (each is one cloud Prover job)")
    p.add_argument("--coverage-target", type=float, default=0.9)
    p.add_argument("--calibrate", action="store_true",
                   help="dump raw certoraRun output to calibrate the result parser")
    args = p.parse_args()

    ok, msg = CertoraVerifier.available()
    if not ok:
        sys.exit(f"[preflight] {msg}")

    sys.exit(run(Path(args.contest), args.conf, args.spec, args.target,
                 args.max_iters, args.coverage_target, args.calibrate, args.max_mutants))


if __name__ == "__main__":
    main()
