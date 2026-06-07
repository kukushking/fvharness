# CVL grounding reference

Concise, conceptual grounding fed into the prover's system prompt. Keep it short and
*correct* — wrong syntax here hurts more than no syntax (cf. the Lean-3-vs-4 failure mode in
../theorem/04-llm-agent/MY_RESULTS.md). Expand it with idioms that work as you learn each
contest; the authoritative source is docs.certora.com.

## Shape of a .spec
- `methods { function balanceOf(address) external returns (uint256) envfree; ... }` —
  declare contract methods; mark `envfree` only when the method genuinely doesn't read
  block/msg context.
- `rule name(env e, ...) { ... assert cond; }` — a property; `assert` is what must hold.
  `require` constrains the starting state (use sparingly — over-`require`ing makes a rule
  vacuous and it will catch no mutants).
- `invariant name(...) cond;` — must hold in every reachable state; the Prover checks it's
  established by the constructor and preserved by every method. Invariants give the broadest
  mutation coverage — prefer them.
- Parametric rules: `rule r(method f, env e, calldataarg args) { ... f(e, args); ... }` —
  quantifies over *all* methods; one rule then constrains the whole contract.

## High-coverage property patterns (these catch the most mutants)
- **Conservation / solvency**: sum of balances == totalSupply; contract holdings >=
  obligations. Use `ghost` + `hook Sstore`/`Sload` to track aggregate state the Prover can't
  see directly.
- **Access control**: only authorized roles can call privileged methods (assert revert
  otherwise).
- **Monotonicity / no-free-mint**: a user's balance can't grow without a corresponding
  transfer/deposit; totalSupply only changes via mint/burn.
- **State-transition integrity**: after `f`, the changed storage matches `f`'s contract.
- **Idempotence / inverse**: deposit-then-withdraw returns to start (modulo fees).

## Tactics
- Ghosts: `ghost mathint sumOfBalances { init_state axiom sumOfBalances == 0; }` with a
  `hook Sstore balances[KEY a] uint v (uint old) { sumOfBalances = sumOfBalances + v - old; }`.
- Use `mathint` for sums to avoid overflow artifacts.
- `requireInvariant` to assume an already-proven invariant inside another rule.
- `assert`, `satisfy`, `require`; `e.msg.sender`, `e.msg.value`, `e.block.timestamp`.

## Discipline
- A rule that reports a counterexample on the *correct* contract is a false positive — fix it
  before adding more. The harness enforces this (constraint 1).
- Broad and sound beats many narrow rules. Reach for invariants and parametric rules first.

---

## Verified idioms (mined from a working ERC20 spec — these compile & verify)

These are the canonical high-coverage patterns for token/DeFi contracts. Adapt the names.

**1. Selector-classification `definition`s** — name the sets of methods that may legitimately
change a quantity, then assert nothing else does:
```cvl
definition canIncreaseBalance(method f) returns bool =
    f.selector == sig:mint(address,uint256).selector ||
    f.selector == sig:transfer(address,uint256).selector ||
    f.selector == sig:transferFrom(address,address,uint256).selector;
definition canDecreaseBalance(method f) returns bool =
    f.selector == sig:burn(address,uint256).selector ||
    f.selector == sig:transfer(address,uint256).selector ||
    f.selector == sig:transferFrom(address,address,uint256).selector;
```

**2. Sum-of-balances conservation** (the single highest-coverage invariant for tokens) —
a ghost tracked by storage hooks, tied to `totalSupply`:
```cvl
ghost mathint sumOfBalances { init_state axiom sumOfBalances == 0; }
hook Sstore _balances[KEY address a] uint256 newValue (uint256 oldValue) {
    sumOfBalances = sumOfBalances - oldValue + newValue;
}
hook Sload uint256 bal _balances[KEY address a] { require sumOfBalances >= bal; }
invariant totalSupplyIsSumOfBalances() totalSupply() == sumOfBalances;
```
(The `Sload` hook restricts a corrupt initial state where one balance exceeds the sum.)

**3. "Only allowed methods may change X" — parametric, the workhorse coverage rule:**
```cvl
rule onlyAllowedMethodsMayChangeBalance(env e) {
    requireInvariant totalSupplyIsSumOfBalances();
    method f; calldataarg args; address holder;
    uint256 before = balanceOf(holder);
    f(e, args);
    uint256 after = balanceOf(holder);
    assert after > before => canIncreaseBalance(f);
    assert after < before => canDecreaseBalance(f);
}
```

**4. Access control:**
```cvl
rule onlyOwnerMintOrBurn(env e) {
    method f; calldataarg args; f(e, args);
    assert f.selector == sig:mint(address,uint256).selector  => e.msg.sender == contractOwner();
    assert f.selector == sig:burn(address,uint256).selector  => e.msg.sender == contractOwner();
}
```

**5. Immutability / monotonicity / filtered parametric:**
```cvl
rule contractOwnerNeverChange(env e) {
    address owner = contractOwner(); method f; calldataarg args; f(e, args);
    assert owner == contractOwner();
}
rule totalSupplyNeverOverflow(env e, method f, calldataarg args)
    filtered { f -> canIncreaseTotalSupply(f) } {
    uint256 before = totalSupply(); f(e, args);
    assert before <= totalSupply();
}
```

Use `mathint` for sums (no overflow artifacts). Pull in proven invariants with
`requireInvariant` before reasoning about a method. These five shapes, instantiated for the
target contract's actual quantities (balances, supply, shares, debt, reserves), catch the
large majority of mutation classes.
