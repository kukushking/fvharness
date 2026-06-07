# State of FV & Bug-Bounty Earning — and AI's Impact

*Snapshot 2026-06-07, compiled from this session's research. Mix of evidence (cited) and
labeled inference. Treat dollar/figure claims as "as of mid-2026, re-check."*

## TL;DR

The venues that let an individual *earn* from smart-contract security are **contracting or
saturating**, and AI is a meaningful part of why. Low-barrier, objective-payout work
(contest findings, micro-bounties) is being commoditized; the value is migrating to **tools,
services, and a thin tier of elite humans**. There is no easy passive "agent prints money"
path here in mid-2026.

## The audit-contest model (Code4rena / Sherlock / Cantina)

- **How it paid:** time-boxed competitions; findings scored by severity with **pro-rata,
  duplicate-decayed** payouts (Sherlock High = 5× Medium ×0.9^(dupes−1)/dupes; Code4rena 10:3
  High:Medium with 0.85 decay). More finders → smaller slice.
- **Top humans did earn big** — milotruck ~$172K (2023), cmichel $1M+ cumulative — but that's
  **elite, full-time, at the 2021–2023 peak**, and cmichel's own data shows hourly rate
  falling ~$2,000 → ~$500 as the crowd grew. Crowd oversupply was eroding economics *before* AI.
- **Now contracting:** Code4rena announced a **wind-down** (completing active contests, then
  shuttering ~late Q2 2026) after pivoting to "free, public-goods" contests — i.e. the
  paid-platform model stopped working. *(CryptoTimes, 2026-05-13.)*

## Formal-verification contests (Certora)

- **Sponsor-gated and sporadic:** run *with* Cantina/Code4rena for specific protocols
  (Aave, Silo, Euler, Uniswap, Blend, Soroban). Pools $100K–$125K; you write CVL specs scored
  by **mutation testing**. Payments handled by the host platform.
- **Effectively dormant:** Certora staff confirmed "no community contests scheduled" — and the
  dry spell runs **~Oct 2025 → June 2026** (no 2026 FV contests found). Not a gap; a stall.
- **Certora the company is fine** (open-sourced the Prover; commercial verification; finding
  compiler/library bugs) — it's the *community-contest* funnel that went quiet, plausibly as
  they tilt toward AI-assisted verification products. *(Inference.)*

## Bug bounties (Immunefi) & OSS bounties (Algora)

- **Immunefi** is still live and large (Critical = direct theft / insolvency; payouts to
  $1M–$10M), but it's **exploit-finding** — the task AI is weakest at (see below).
- **OSS bounties (Algora):** real but **thin and mostly uncapturable on inspection**. A live
  board sampled ~$11K open, but per-issue checks showed the money is **contested** (one $100
  issue had 4 open PRs racing it), **merge-gated** (a Cal.com bounty open 3.5 yrs with stalled
  PRs — maintainer never merges), or **interview-gated** (an Archestra bounty "reserved for
  software-engineering interviews"). Algora's own site now leads with **recruiting**, not the
  bounty marketplace.

## AI's impact (the throughline)

- **Capability is real but bounded.** Paradigm + OpenAI's **EVMbench** (Feb 2026) benchmarks
  AI auditors; an independent re-evaluation (arXiv 2603.10795) found detection **peaks ~47.5%**
  and **0% end-to-end real-world exploitation** across 110 agent-incident pairs. No AI has a
  *confirmed* contest win (the "Octane #1 on Code4rena" claim was refuted). The viable model is
  **human-in-the-loop**: agents do breadth, humans do depth/adversarial reasoning.
- **Market effect is the bigger story.** Even imperfect AI first-pass tooling reduces how many
  human wardens a sponsor needs, compressing crowd payouts — and AI-drafted specs reduce the
  need to *crowdsource* human spec-writers. Layered on pre-existing oversupply, this is
  plausibly **~60–70% of why the contest/bounty model is shrinking** *(inference, not proven;
  crypto market cycles and company-specific factors also matter)*.
- **The pattern:** AI **destroys** value in low-barrier crowd-labor venues (auditing contests,
  micro-bounties) and **creates** value where it's the *tool* or where the problem is
  *objectively scored and hard*. Trying to use an agent to out-race humans in the shrinking
  crowd-labor venues fights the very tide AI is creating.

## Honest takeaways for earning here

1. **Don't chase low-barrier objective payouts** — they're saturated, gated, or eroding.
2. **The money that's left is either hard or real work:** frontier objective comps (ARC,
   Hutter — big, uncontested-because-hard, low win odds) **or** becoming/​building the thing
   protocols pay for (a skilled FV/security engineer, or a tool/service).
3. **"$200K in FV" is a salary, not contest winnings** — a career/skill or product path
   measured in months, not a harness you run.
4. **Verify before building:** confirm a live, open, payable, *winnable-by-you* opportunity
   (entry mechanics, competition, merge/payout gates on real listings) before investing effort.

## What I'd actually try if forced to pick

Opinionated, given *this* builder's assets — strong agentic-harness engineering, a math/ATP
(Lean) background (`~/Projects/theorem`), Claude Code fluency, and the working CVL/mutation
harness + fresh Certora skill from this session. Ranked by realistic odds of real money,
honest about effort and EV.

**#1 (what I'd actually do) — Turn the FV skill into paid work, not contest winnings.**
The "$200K" in this space is a *salary/contract rate for a skilled FV/security engineer*, and
that path is real and not saturated the way contests are. Concretely: run the harness over
**2–3 public past Certora contest repos** (silo-v2, euler-vault, uniswap-v4-periphery —
already clonable, the harness runs them), **publish the specs + writeups** as a portfolio,
and pitch audit firms / protocols / Certora-adjacent shops with an angle no human auditor
has: *"agentic FV — I write invariant suites with an LLM-in-the-loop harness."* Salvages
today's effort instead of discarding it. Months of real work; high ceiling; highest
probability of a real income number. **This is the pick.**

**#2 — Productize the agentic-verification capability.** Generalize what we built into a
narrow tool: *point it at a Foundry/Solidity repo → it drafts an invariant test suite or a
starter CVL spec.* The market is visibly moving toward AI-assisted verification (Certora
itself, EVMbench), so the tailwind is real — but you can't out-build Certora, so win on
*narrow + cheap + self-serve* for small protocols, or open-source it and sell consulting.
Higher ceiling, higher risk, startup-shaped. Only if you want to build a product, not a job.

**#3 (the fun high-variance side bet) — ARC Prize 2026.** It's objectively scored, big, and
*uncontested-because-hard* — and ARC-AGI is reasoning/program-synthesis, which actually fits
your brain and your harness-building edge better than auditing ever did. The **Milestone #1
(June 30: $25K/$10K/$2.5K)** is the most plausible non-lottery slice. Treat as a long-odds
side bet you'd enjoy, not as income.

**#4 — Bounties, but only as a stopgap done right.** Don't race $100 issues. Pick **one**
in-domain org (your MCP/agent fluency → Archestra-type repos), contribute repeatedly, build
standing until work gets *assigned* or a contract/hire follows. Converts racing into a
relationship. Modest money, but the honest version.

**What I'd skip:** Certora community contests (dormant), Code4rena (shutting down), generic
OSS bounty-racing (contested/merge-gated), Immunefi exploit-hunting (AI's weakest task,
elite-human territory), Hutter Prize (deep niche, not your background).

**The meta-move:** stop hunting for a venue where an agent prints passive money — every one
we checked evaporated. Use the agentic capability as **leverage on real work or a real
product**, and let the "objective payout" be a *salary, a client invoice, or a milestone
prize* rather than a crowd-labor race AI is busy commoditizing.

## Sources

- Code4rena wind-down — cryptotimes.io/2026/05/13/code4rena-announces-wind-down…
- Certora contests / repos — certora.com/contests; github.com/Certora/{silo-v2,euler-vault,uniswap-v4-periphery}-cantina-fv
- Payout mechanics — docs.code4rena.com/awarding; docs.sherlock.xyz; immunefi.com (v2.3 severity)
- Earnings — milotruck.github.io/blog/A-year-of-Competitive-Audits; cmichel.io/code4rena-first-1m-stats
- AI — paradigm.xyz/2026/02/evmbench; openai.com/index/introducing-evmbench; arxiv.org/pdf/2603.10795
- OSS bounties — algora.io/bounties (live board inspected 2026-06-07)
