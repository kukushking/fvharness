# Example outputs (2026-06-07)

Specs written by the harness, unedited. Each verified on the original contract via the
Certora cloud Prover; reports below are owner-scoped (shareable links come from the dashboard).

## erc20/ — Certora `DEFI/ERC20` (OpenZeppelin-style, 425 lines, no starting spec)

`Generated.spec` — 17 rules + 2 invariants, converged at iteration 2. Verifies on the
original; catches 6/6 locally generated mutants. `runGenerated.conf` is the exact conf used.

Prover runs:
- https://prover.certora.com/output/8535569/31b4d0474428494681ecf115544b4c8e
- https://prover.certora.com/output/8535569/5f44746efe604960af391ed41a847aa4
- https://prover.certora.com/output/8535569/b9361ab6992349a18fab6745af813d3e

## ballgame/ — Certora `CVLByExample/Invariant`

`BallGameCorrect.spec` — iteration 1; rediscovers the inductive strengthening the example
teaches (`ballPosition() == 1 || == 3`), verifies, catches 2/2 mutants.

Prover runs:
- https://prover.certora.com/output/8535569/7197b99d4a1543f796ff70556b5abaef
- https://prover.certora.com/output/8535569/75e15f6340aa4ca3a9ba42bb999ae1e7
- https://prover.certora.com/output/8535569/dedc34ba47c649889bb7185f8da8f846
- https://prover.certora.com/output/8535569/fb45fcf9c3b04f7aa7761779a8845806
