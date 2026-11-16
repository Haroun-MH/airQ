"""Temporary proof that a failing test blocks the pull request."""


def test_red_proof() -> None:
    assert False, "intentional failure used to prove that CI blocks the merge"
