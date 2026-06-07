/*
 * Certora spec for ERC20 (Solmate-style).
 * Core safety properties: supply == sum of balances, balance bounds,
 * access control on mint/burn, allowance integrity, and per-method
 * state-transition correctness.
 */

methods {
    function totalSupply()                       external returns (uint256) envfree;
    function balanceOf(address)                  external returns (uint256) envfree;
    function allowance(address,address)          external returns (uint256) envfree;
    function nonces(address)                     external returns (uint256) envfree;
    function contractOwner()                     external returns (address) envfree;
    function decimals()                          external returns (uint8)   envfree;

    function approve(address,uint256)            external returns (bool);
    function transfer(address,uint256)           external returns (bool);
    function transferFrom(address,address,uint256) external returns (bool);
    function mint(address,uint256)               external;
    function burn(address,uint256)               external;
}

/*//////////////////////////////////////////////////////////////
                  GHOST: SUM OF ALL BALANCES
//////////////////////////////////////////////////////////////*/

ghost mathint sumOfBalances {
    init_state axiom sumOfBalances == 0;
}

hook Sstore _balances[KEY address a] uint256 newValue (uint256 oldValue) {
    sumOfBalances = sumOfBalances - oldValue + newValue;
}

hook Sload uint256 bal _balances[KEY address a] {
    require sumOfBalances >= to_mathint(bal);
}

/*//////////////////////////////////////////////////////////////
                       CORE INVARIANTS
//////////////////////////////////////////////////////////////*/

/// totalSupply is always exactly the sum of all balances.
invariant totalSupplyIsSumOfBalances()
    to_mathint(totalSupply()) == sumOfBalances;

/// Any single balance never exceeds totalSupply.
invariant balanceBoundedByTotalSupply(address a)
    balanceOf(a) <= totalSupply()
    { preserved { requireInvariant totalSupplyIsSumOfBalances(); } }

/*//////////////////////////////////////////////////////////////
              METHOD-CLASSIFICATION DEFINITIONS
//////////////////////////////////////////////////////////////*/

definition canChangeBalance(method f) returns bool =
    f.selector == sig:transfer(address,uint256).selector ||
    f.selector == sig:transferFrom(address,address,uint256).selector ||
    f.selector == sig:mint(address,uint256).selector ||
    f.selector == sig:burn(address,uint256).selector;

definition canIncreaseTotalSupply(method f) returns bool =
    f.selector == sig:mint(address,uint256).selector;

definition canDecreaseTotalSupply(method f) returns bool =
    f.selector == sig:burn(address,uint256).selector;

definition canChangeTotalSupply(method f) returns bool =
    canIncreaseTotalSupply(f) || canDecreaseTotalSupply(f);

definition canChangeAllowance(method f) returns bool =
    f.selector == sig:approve(address,uint256).selector ||
    f.selector == sig:transferFrom(address,address,uint256).selector ||
    f.selector == sig:permit(address,address,uint256,uint256,uint8,bytes32,bytes32).selector;

/*//////////////////////////////////////////////////////////////
                 PARAMETRIC STATE-CHANGE RULES
//////////////////////////////////////////////////////////////*/

/// Only the whitelisted methods may change a holder's balance.
rule onlyAllowedMethodsMayChangeBalance(env e, method f, calldataarg args, address holder) {
    requireInvariant totalSupplyIsSumOfBalances();
    uint256 before = balanceOf(holder);
    f(e, args);
    uint256 after = balanceOf(holder);
    assert after != before => canChangeBalance(f);
}

/// Only mint/burn may change totalSupply.
rule onlyMintBurnChangeTotalSupply(env e, method f, calldataarg args) {
    requireInvariant totalSupplyIsSumOfBalances();
    uint256 before = totalSupply();
    f(e, args);
    uint256 after = totalSupply();
    assert after > before => canIncreaseTotalSupply(f);
    assert after < before => canDecreaseTotalSupply(f);
}

/// Only approve/transferFrom/permit may change an allowance.
rule onlyAllowedMethodsMayChangeAllowance(env e, method f, calldataarg args,
                                          address owner, address spender) {
    uint256 before = allowance(owner, spender);
    f(e, args);
    uint256 after = allowance(owner, spender);
    assert after != before => canChangeAllowance(f);
}

/// totalSupply never overflows on mint.
rule totalSupplyMonotonicOnMint(env e, calldataarg args) {
    requireInvariant totalSupplyIsSumOfBalances();
    uint256 before = totalSupply();
    mint(e, args);
    assert totalSupply() >= before;
}

/// totalSupply never increases on burn.
rule totalSupplyMonotonicOnBurn(env e, calldataarg args) {
    requireInvariant totalSupplyIsSumOfBalances();
    uint256 before = totalSupply();
    burn(e, args);
    assert totalSupply() <= before;
}

/*//////////////////////////////////////////////////////////////
                       ACCESS CONTROL
//////////////////////////////////////////////////////////////*/

/// Only the owner can mint or burn.
rule onlyOwnerMintOrBurn(env e, method f, calldataarg args)
    filtered { f -> canChangeTotalSupply(f) }
{
    address owner = contractOwner();
    f(e, args);
    assert e.msg.sender == owner;
}

/// Owner never changes.
rule contractOwnerNeverChanges(env e, method f, calldataarg args) {
    address ownerBefore = contractOwner();
    f(e, args);
    assert contractOwner() == ownerBefore;
}

/*//////////////////////////////////////////////////////////////
                  FUNCTIONAL CORRECTNESS
//////////////////////////////////////////////////////////////*/

/// approve sets exactly the requested allowance.
rule approveSetsAllowance(env e, address spender, uint256 amount) {
    approve(e, spender, amount);
    assert allowance(e.msg.sender, spender) == amount;
}

/// transfer moves the exact amount between distinct accounts.
rule transferIntegrity(env e, address to, uint256 amount) {
    requireInvariant totalSupplyIsSumOfBalances();
    require e.msg.sender != to;
    uint256 fromBefore = balanceOf(e.msg.sender);
    uint256 toBefore   = balanceOf(to);

    transfer(e, to, amount);

    assert balanceOf(e.msg.sender) == assert_uint256(fromBefore - amount);
    assert balanceOf(to)           == assert_uint256(toBefore + amount);
}

/// transfer to self preserves balance.
rule transferToSelfNoEffect(env e, uint256 amount) {
    uint256 before = balanceOf(e.msg.sender);
    transfer(e, e.msg.sender, amount);
    assert balanceOf(e.msg.sender) == before;
}

/// transfer cannot exceed available balance (must revert otherwise).
rule transferRevertsOnInsufficientBalance(env e, address to, uint256 amount) {
    require balanceOf(e.msg.sender) < amount;
    transfer@withrevert(e, to, amount);
    assert lastReverted;
}

/// transferFrom decreases allowance by exactly amount when not infinite.
rule transferFromDecreasesAllowance(env e, address from, address to, uint256 amount) {
    uint256 allowBefore = allowance(from, e.msg.sender);
    require allowBefore != max_uint256;

    transferFrom(e, from, to, amount);

    assert allowance(from, e.msg.sender) == assert_uint256(allowBefore - amount);
}

/// transferFrom with infinite allowance leaves allowance unchanged.
rule transferFromInfiniteAllowanceUnchanged(env e, address from, address to, uint256 amount) {
    require allowance(from, e.msg.sender) == max_uint256;
    transferFrom(e, from, to, amount);
    assert allowance(from, e.msg.sender) == max_uint256;
}

/// transferFrom moves exact amount between distinct accounts.
rule transferFromIntegrity(env e, address from, address to, uint256 amount) {
    requireInvariant totalSupplyIsSumOfBalances();
    require from != to;
    uint256 fromBefore = balanceOf(from);
    uint256 toBefore   = balanceOf(to);

    transferFrom(e, from, to, amount);

    assert balanceOf(from) == assert_uint256(fromBefore - amount);
    assert balanceOf(to)   == assert_uint256(toBefore + amount);
}

/// mint increases recipient balance and totalSupply by amount.
rule mintIntegrity(env e, address to, uint256 amount) {
    requireInvariant totalSupplyIsSumOfBalances();
    uint256 supplyBefore = totalSupply();
    uint256 balBefore    = balanceOf(to);

    mint(e, to, amount);

    assert totalSupply()  == assert_uint256(supplyBefore + amount);
    assert balanceOf(to)  == assert_uint256(balBefore + amount);
}

/// burn decreases holder balance and totalSupply by amount.
rule burnIntegrity(env e, address from, uint256 amount) {
    requireInvariant totalSupplyIsSumOfBalances();
    uint256 supplyBefore = totalSupply();
    uint256 balBefore    = balanceOf(from);

    burn(e, from, amount);

    assert totalSupply()  == assert_uint256(supplyBefore - amount);
    assert balanceOf(from) == assert_uint256(balBefore - amount);
}

/// A method never changes the balance of an account it doesn't reference.
rule noUnexpectedThirdPartyBalanceChange(env e, method f, calldataarg args,
                                         address a, address b, address other) {
    requireInvariant totalSupplyIsSumOfBalances();
    uint256 before = balanceOf(other);
    f(e, args);
    uint256 after = balanceOf(other);
    assert after != before => canChangeBalance(f);
}
