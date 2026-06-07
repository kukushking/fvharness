# fvharness — agentic formal verification for smart contracts

An LLM writes [Certora](https://www.certora.com/) **CVL specifications**, the **Certora Prover**
verifies them, and a **mutation-testing loop** scores how many injected bugs the spec catches —
then feeds failures back and iterates. Generate → verify → score → repeat, with the Prover as
unfakeable ground truth.

> The point: formal verification is uniquely friendly to an LLM-in-the-loop, because the
> verifier gives a **mechanical, unfakeable pass/fail signal**. The model can be wrong; the
> kernel can't be fooled. So you let the model generate and let the Prover judge — exactly the
> shape that works for LLM theorem-proving, applied to smart-contract security.

## What it produces — a worked result

Pointed at a real **425-line ERC-20** (OpenZeppelin-style) with no starting spec, the harness:

1. **Iteration 1** — wrote a full CVL spec; the Prover found **3 rules were false positives** on
   the correct contract (`onlyMintBurnChangeTotalSupply`, `totalSupplyMonotonicOnBurn`,
   `twoBalancesBoundedByTotalSupply`). The loop fed the exact offending rule names back.
2. **Iteration 2** — corrected those rules; the spec now **verifies on the original contract**
   *and* **catches 6/6 injected mutants → 100% mutation coverage.** Stopped.

The converged spec is **~18 rules + 2 invariants + 5 method-classification definitions** —
conservation of supply (`totalSupply == Σ balances` via a ghost + storage hooks), access
control (only owner mints/burns), supply monotonicity, and transfer/mint/burn integrity —
comparable in scope to Certora's own reference ERC-20 spec, written from scratch by the loop.

Every run emits a **`prover.certora.com` report** that anyone can open and check — the result
is independently verifiable, not a claim. *(Reports are owner-scoped by default; shareable
`anonymousKey` links are generated from the Certora dashboard.)*

On a smaller didactic contract it also rediscovered the **inductive strengthening** that the
example exists to teach (a non-inductive safety property has to be strengthened to verify) —
i.e. it isn't pattern-matching boilerplate, it's doing the actual FV reasoning.

See [`examples/`](examples/) for the converged specs, confs and Prover report links.

## How the scoring works (and why it fits an LLM loop)

Certora FV contests score a spec by **mutation testing**: inject a bug into the contract, and a
good spec **catches** it (some rule flips to violated on the buggy code while staying verified on
the correct code). A spec that passes on buggy code is worthless. So the loop enforces two
constraints, in order:

1. **No false positives** — every rule must verify on the *correct* contract (else the offending
   rules are fed back for repair).
2. **Catch mutants** — surviving mutants are fed back so the next spec widens coverage.
   `coverage = mutants_caught / mutants_total` is the optimization target.

Because the official mutation report isn't machine-readable, the harness runs its **own** local
mutation loop (generated mutants + any provided public ones) to get a programmatic coverage
signal to optimize against.

## Architecture

```
src/fvharness/
  prover.py     CvlProver — Claude Opus 4.8 (adaptive thinking, high effort) writes/repairs CVL
  certora.py    CertoraVerifier — wraps `certoraRun`, parses per-rule verdicts (calibrated)
  mutation.py   MutationHarness — generates mutants, scores coverage (the reward signal)
  context.py    builds the prompt: contract source + scope + CVL idiom reference + prior errors
  loop.py       the agent loop: propose → verify-on-original → score-vs-mutants → feed back
cvl_reference/  verified high-coverage CVL idioms used to ground the model
```

## Run it

```bash
pip install certora-cli            # certoraRun + certoraMutate
# (optional) a real JDK enables fast local CVL typechecking: brew install openjdk@21
uv sync
export CERTORAKEY=...              # free personal key from certora.com/signup?plan=prover
export FVHARNESS_ANTHROPIC_KEY=... # the harness's own Anthropic key

uv run fvharness --contest contests/<repo> --conf <path/to.conf> --max-iters 5
```

The harness verifies the spec on the original contract, scores it against mutants, keeps the
best, and writes it to the path in the conf's `verify` field.

## Honest scope & limitations

- **Proven on self-contained real contracts (ERC-20).** It writes verifying, mutation-catching
  CVL on a genuine contract — not a toy.
- **Production-protocol contests are the next step, not done.** A full contest harness (e.g. a
  lending protocol) needs the whole build environment — linked contracts, mocks, package
  remappings, ~1-hour Prover jobs. That's an infrastructure lift; the harness logic carries over,
  but it hasn't been run end-to-end at that scale here.
- **Self-generated mutants are a proxy** for a contest's private mutants. Broad invariants that
  kill ours should generalize, but coverage here ≠ contest coverage.
- **Not a moat.** AI-assisted verification is an active frontier (Certora itself is building in
  this direction). The value is the *combination* — formal-methods fluency plus agentic
  engineering — and a verifier-grounded loop that keeps the model honest.

## Notes

Built as a focused exploration with [Claude Code](https://claude.com/claude-code). The
verifier-as-ground-truth pattern is borrowed from LLM theorem-proving (Lean kernel → Certora
Prover); the CVL idiom reference (`cvl_reference/`) was mined from working Certora specs.
