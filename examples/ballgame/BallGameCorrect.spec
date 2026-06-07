methods {
    function ballPosition() external returns (uint8) envfree;
}

/// The ball can only ever be held by player 1 or player 3.
/// This is the strengthened invariant that implies player 2 never gets the ball.
invariant ballOnlyAtOneOrThree()
    ballPosition() == 1 || ballPosition() == 3;

/// The original (weaker) safety goal: player 2 never receives the ball.
/// Proven using the stronger invariant above.
invariant playerTwoNeverReceivesBall()
    ballPosition() != 2
    {
        preserved {
            requireInvariant ballOnlyAtOneOrThree();
        }
    }

/// Parametric rule: after any method, the ball remains at player 1 or 3.
rule ballStaysValid(method f, env e, calldataarg args) {
    requireInvariant ballOnlyAtOneOrThree();
    require ballPosition() == 1 || ballPosition() == 3;
    f(e, args);
    assert ballPosition() == 1 || ballPosition() == 3,
        "ball must remain at player 1 or 3 after any operation";
}

/// pass() always toggles between 1 and 3.
rule passTogglesBall(env e) {
    requireInvariant ballOnlyAtOneOrThree();
    uint8 before = ballPosition();
    pass(e);
    uint8 after = ballPosition();
    assert (before == 1 => after == 3) && (before == 3 => after == 1),
        "pass must toggle the ball between players 1 and 3";
}

/// The ball position is always one of the valid player numbers (never 0 or >4).
invariant ballPositionInRange()
    ballPosition() == 1 || ballPosition() == 3
    {
        preserved {
            requireInvariant ballOnlyAtOneOrThree();
        }
    }
