import pytest


@pytest.fixture
def ist():
    def ist(a, b=None, key=None):
        if key is None:
            if b is not None:
                assert a == b
            else:
                assert a
        else:
            if b is not None:
                assert key(a, b)
            else:
                assert key(a)
    return ist
