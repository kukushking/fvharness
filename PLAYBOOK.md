# Certora FV Contest Playbook

*Verified workflow + scoring, distilled from deep research (2026-06-07). Sources: certora.com/contests, alexzoid.com practical guide, docs.certora.com. Re-check before each contest — terms move.*

## What the contest is

You are given a real protocol's Solidity, a `certora/` directory with `.conf` files, and
(usually) a set of **public mutants**. You write **CVL specifications** — `rule`s and
`invariant`s — in `.spec` files. You submit a **private GitHub repo** with the judges added
as collaborators. After the deadline, the judges run mutation testing against your specs.

You are **not** finding exploits. You are writing correctness properties that the **Certora
Prover** mechanically verifies. This is why it fits an LLM+verifier+iterate loop: the Prover
is unfakeable ground truth, exactly like the Lean kernel in `../theorem`.

## How you win — the scoring (this drives the whole harness)

A spec is scored by **mutation testing**: take the original (correct) code, inject a bug
(a *mutant*), and check whether your spec **catches** it (some rule flips to VIOLATED on the
mutant while staying VERIFIED on the original). A spec that passes on a *buggy* contract is
worthless — "vacuous or not rigorous enough."

Prize pools (per alexzoid) typically split roughly:

| Bucket | ~Weight | What it rewards |
|---|---|---|
| Participation | ~10% | Properties that catch the **public** mutants (provided at start) |
| Real bugs | ~20% | Catching legitimate bugs within FV scope |
| **Coverage** | **~70%** | Catching **private** mutants (held by judges), **weighted so the fewer entrants catch a mutant, the more it pays** |

**Strategic implications baked into the harness:**
1. **Two hard constraints, in order:** (a) every rule must **pass on the original** (no false
   positives — a rule that's wrong on correct code is disqualified/useless), then (b) it must
   **catch mutants**.
2. **Broad, high-level invariants beat narrow rules.** alexzoid's example: one high-level
   invariant caught all 3 public mutants in the Euler contest. Coverage breadth — not rule
   count — is the payout driver.
3. **Rare catches pay most.** The 70% bucket rewards catching mutants few others catch, so
   after covering the obvious, hunt the deep/unusual properties.

## The tooling

- `pip install certora-cli` → provides `certoraRun` and `certoraMutate`.
- **Needs a Prover key** in `CERTORAKEY` (env var). You get one when you enter a contest;
  the Prover runs in Certora's cloud (prover.certora.com).
- `certoraRun certora/confs/X.conf --wait_for_results ALL` — runs the Prover, **blocks**, and
  the return code reflects whether violations were found. This is our programmatic pass/fail.
- `.conf` is JSON5: `{"files":[...], "verify":"Contract:path.spec", "rule":[...], "solc":"...",
  "msg":"..."}`.
- `certoraMutate <conf>` — runs Gambit to generate mutants and reports caught/survived, **but
  the report is dashboard-only** (prover.certora.com/mutations) — no documented JSON export.
- Repo layout: `certora/{confs,specs,mutations}/`, plus `forge build` for the Solidity.

## How the harness exploits this

Because the official mutation report is dashboard-only, we build our **own local mutation
loop** for the iterate signal (see `src/fvharness/mutation.py`):

```
LLM writes CVL spec
   → certoraRun on ORIGINAL        (constraint a: must pass — else feed FP back)
   → for each mutant we generate:  certoraRun on MUTANT
        caught  = a baseline-VERIFIED rule is now VIOLATED
        survived = mutant slips through  → feed the surviving mutant back to the LLM
   → score = caught / total; keep best spec; iterate to widen coverage
```

Mutants come from: (1) the contest's provided **public mutants** (`mutations/`), and
(2) a **built-in mutator** that injects common bug classes (operator/comparator swaps,
`require` removal, off-by-one) so the loop has a reward signal before/without cloud mutation.
Our self-generated mutants are a *proxy* for the judges' private mutants — broad specs that
kill ours should generalize. (Honest caveat: it's a proxy, not the real private set.)

## Open questions to resolve on first real run

- Exact `certoraRun --wait_for_results` stdout/results format for **per-rule** verdicts
  (parser in `certora.py` is best-effort + return-code fallback; calibrate on run 1).
- Whether `certoraMutate` has any machine-readable output we can parse instead of our local
  mutator.
- Median (non-top) earnings per contest — unknown; treat as "shot at $1k–$10k placements +
  moat-building," not guaranteed income.
