"""Import-time notices for the legacy alpha APIs."""

from __future__ import annotations

import subprocess
import sys


def test_alpha_selection_warns_once_per_import_in_fresh_process() -> None:
    source = """
import importlib
import warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always', DeprecationWarning)
    importlib.import_module('hubbardflow.domain.alpha_selection')
    importlib.import_module('hubbardflow.domain.alpha_selection')
messages = [str(item.message) for item in caught if issubclass(item.category, DeprecationWarning)]
assert messages == ['hubbardflow.domain.alpha_selection is deprecated; see FD-EBQ review §M.1']
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_adaptive_alpha_warns_once_and_dependency_notice_is_once() -> None:
    source = """
import importlib
import warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always', DeprecationWarning)
    importlib.import_module('hubbardflow.domain.adaptive_alpha')
    importlib.import_module('hubbardflow.domain.adaptive_alpha')
messages = [str(item.message) for item in caught if issubclass(item.category, DeprecationWarning)]
assert messages.count('hubbardflow.domain.alpha_selection is deprecated; see FD-EBQ review §M.1') == 1
assert messages.count('hubbardflow.domain.adaptive_alpha is deprecated; see FD-EBQ review §M.1') == 1
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
