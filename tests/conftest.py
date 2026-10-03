from pathlib import Path

import numpy as np
import pytest

_KNOWN_FAILURES = Path(__file__).with_name("known_failures.txt")
_known_failure_rows = [
    tuple(part.strip() for part in line.split("|", maxsplit=2))
    for line in _KNOWN_FAILURES.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]
collect_ignore = [
    file_path
    for kind, file_path, _reason in _known_failure_rows
    if kind == "collect_ignore"
]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Quarantine only known baseline failures whose stated fixture is absent."""
    root = _KNOWN_FAILURES.parent.parent
    failures = {
        node_id: reason
        for kind, node_id, reason in _known_failure_rows
        if kind == "xfail"
    }
    for item in items:
        reason = failures.get(item.nodeid)
        if reason is None:
            continue
        if reason.startswith("missing file: "):
            missing_path = root / reason.removeprefix("missing file: ")
            if missing_path.exists():
                continue
        item.add_marker(pytest.mark.xfail(reason=reason, strict=True))


@pytest.fixture
def A_2x4():
    return np.array([[1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0]])


@pytest.fixture
def ALPHA_SYMMETRIC():
    return [-0.10, -0.05, 0.00, 0.05, 0.10]


@pytest.fixture
def INTERCEPTS():
    return np.array([2.5, 2.5, 2.5, 2.5])


@pytest.fixture
def R_BARE_C1():
    return np.array([[-0.50, -0.05], [-0.50, -0.05], [-0.05, -0.50], [-0.05, -0.50]])

@pytest.fixture
def R_SCR_C1():
    return np.array([[-0.40, -0.04], [-0.40, -0.04], [-0.04, -0.40], [-0.04, -0.40]])


@pytest.fixture
def U_TRUE_C1():
    return np.array([[0.25252525252525254, -0.025252525252525245], [-0.025252525252525245, 0.25252525252525254]])
