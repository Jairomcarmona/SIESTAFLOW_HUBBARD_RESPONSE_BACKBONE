from __future__ import annotations

import hashlib

from tools.extract_lr06_trace import render_fixture_from_lines


def test_fixture_renderer_uses_only_the_documented_native_line_ranges() -> None:
    lines = [f"source line {line_number}" for line_number in range(1, 4580)]

    rendered = render_fixture_from_lines(lines)

    assert "# Native output line 4337; production profile signature:\nsource line 4337\n" in rendered
    assert "# Native output lines 4483-4514; complete pre-perturbation population event:\n" in rendered
    assert "source line 4483\n" in rendered
    assert "source line 4514\n" in rendered
    assert "# Native output lines 4515-4579; verbatim trace lines 70-134:\n" in rendered
    assert "source line 4515\n" in rendered
    assert "source line 4579\n" in rendered
    assert "source line 4336\n" not in rendered
    assert "source line 4482\n" not in rendered
    assert "source line 4580\n" not in rendered

    selected_parent = "\n".join(lines[4482:4514]) + "\n"
    expected_parent_digest = hashlib.sha256(selected_parent.encode("utf-8")).hexdigest()
    assert f"# Extracted section native lines 4483-4514 SHA-256: {expected_parent_digest}" in rendered
