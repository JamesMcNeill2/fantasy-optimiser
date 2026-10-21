import pytest


def test_deliberate_ci_failure():
    pytest.fail("deliberate CI failure")
