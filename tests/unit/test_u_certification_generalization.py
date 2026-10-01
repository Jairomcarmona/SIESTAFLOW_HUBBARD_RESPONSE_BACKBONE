from copy import deepcopy
import ast
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import re
import random

import pytest

from hubbardflow.domain.u_certification import CertificationError, certify_u_matrices
from hubbardflow.domain.u_repeatability import repeatability_envelope
from hubbardflow.execution.u_certification_node import UCertificationNodeError, _derive_boxes


ACTIVE = ["-0.037", "-0.014", "-0.006", "0.006", "0.014", "0.037"]
EXTRA = ["-0.123", "-0.077", "0.077", "0.123"]
def _dataset(site_ids, active=ACTIVE, extra=(), external_shift="0"):
    n = len(site_ids)
    bare = [[Fraction(4 + i, 1) if i == j else Fraction(i + j + 1, 20) for j in range(n)] for i in range(n)]
    screened = [[Fraction(2 + i, 1) if i == j else Fraction(i + j + 1, 30) for j in range(n)] for i in range(n)]
    observations = []
    for mode, matrix in (("BARE", bare), ("SCREENED", screened)):
        for j, site in enumerate(site_ids):
            for alpha in [*active, *extra]:
                x = Fraction(alpha)
                shift = Fraction(external_shift) if alpha in extra else Fraction(0)
                tokens = [f"{Decimal(10 + i) + Decimal(x.numerator) / Decimal(x.denominator) * (Decimal(matrix[i][j].numerator) / Decimal(matrix[i][j].denominator)) + Decimal(shift.numerator) / Decimal(shift.denominator):.12f}" for i in range(n)]
                observations.append({
                    "mode": mode, "perturbed_site_index": j, "perturbed_site_id": site,
                    "alpha_token": alpha, "occupation_tokens": [[value] for value in tokens],
                })
    return {
        "schema_version": "response_tokens.v1", "status": "AVAILABLE", "campaign_uuid": "synthetic",
        "matrix_dimension": n, "polynomial_degree": 1, "observations": observations,
    }


def _certify(dataset, active=ACTIVE):
    bare, screened = _derive_boxes(dataset, active)
    return bare, screened, certify_u_matrices(bare, screened)


def test_arbitrary_synthetic_2x2_uses_only_the_six_committed_active_points(monkeypatch):
    dataset = _dataset(("X17", "Q42"), extra=("-0.091", "0.091"), external_shift="100")
    selected = []
    from hubbardflow.execution import u_certification_node
    original = u_certification_node.exact_slope_weights

    def capture(alphas, degree):
        selected.append(tuple(alphas))
        return original(alphas, degree)

    monkeypatch.setattr(u_certification_node, "exact_slope_weights", capture)
    _derive_boxes(dataset, ACTIVE)
    assert len(selected) == 4
    assert all(values == tuple(ACTIVE) for values in selected)
    assert "-0.091" not in selected[0] and "0.091" not in selected[0]


def test_external_alpha_values_do_not_change_scientific_certification():
    base = _dataset(("X17", "Q42"))
    augmented = _dataset(("X17", "Q42"), extra=EXTRA, external_shift="900")
    base_bare, base_screened, base_result = _certify(base)
    extra_bare, extra_screened, extra_result = _certify(augmented)
    assert (extra_bare, extra_screened) == (base_bare, base_screened)
    for key in ("u_interval_by_site", "half_width_by_site", "method", "consistency_status"):
        assert extra_result[key] == base_result[key]


def test_missing_active_alpha_fails_without_nearest_point_substitution():
    data = _dataset(("X17", "Q42"), extra=("0.040",))
    data["observations"] = [row for row in data["observations"] if not (
        row["mode"] == "BARE" and row["perturbed_site_index"] == 1 and row["alpha_token"] == "0.037"
    )]
    with pytest.raises(UCertificationNodeError, match="active analysis alpha coverage is incomplete"):
        _derive_boxes(data, ACTIVE)


def test_duplicate_active_cell_is_rejected_even_if_tokens_agree():
    data = _dataset(("X17", "Q42"))
    data["observations"].append(deepcopy(data["observations"][0]))
    with pytest.raises(UCertificationNodeError, match="duplicate response alpha coverage"):
        _derive_boxes(data, ACTIVE)


def test_site_rename_preserves_matrices_and_changes_only_semantic_identity():
    named = _dataset(("site_A", "site_B"))
    renamed = _dataset(("foobar", "quux_918"))
    named_boxes = _certify(named)
    renamed_boxes = _certify(renamed)
    assert named_boxes == renamed_boxes
    from hubbardflow.execution.source_evidence import scientific_tokens_sha256
    assert scientific_tokens_sha256(named) != scientific_tokens_sha256(renamed)


def test_site_permutation_permutes_rows_columns_and_u_intervals():
    original = _dataset(("site_A", "site_B"))
    permutation = (1, 0)
    relabeled = deepcopy(original)
    # Simultaneously permute site order, perturbed columns, and observed rows.
    for row in relabeled["observations"]:
        row["occupation_tokens"] = list(reversed(row["occupation_tokens"]))
        row["perturbed_site_index"] = permutation[row["perturbed_site_index"]]
        row["perturbed_site_id"] = ("site_B", "site_A")[row["perturbed_site_index"]]
    old_bare, old_screened, old_u = _certify(original)
    new_bare, new_screened, new_u = _certify(relabeled)
    for old, new in ((old_bare, new_bare), (old_screened, new_screened)):
        for i in range(2):
            for j in range(2):
                assert new[i][j] == old[permutation[i]][permutation[j]]
    assert new_u["u_interval_by_site"] == [old_u["u_interval_by_site"][1], old_u["u_interval_by_site"][0]]


def test_token_record_order_does_not_change_certification():
    data = _dataset(("X17", "Q42"), extra=EXTRA)
    expected = _certify(data)
    random.Random(71).shuffle(data["observations"])
    assert _certify(data) == expected


def test_generic_n3_with_irregular_grid_and_external_alphas_is_certified():
    sites = ("S0", "S1", "S2")
    active = ACTIVE
    clean = _dataset(sites, active=active)
    with_extra = _dataset(sites, active=active, extra=EXTRA, external_shift="500")
    bare, screened, result = _certify(with_extra, active)
    clean_bare, clean_screened, clean_result = _certify(clean, active)
    assert len(bare) == len(screened) == 3
    assert result["status"] in {"CERTIFIED", "CERTIFIED_WITH_FALLBACK"}
    assert result["method"] in {"verified_krawczyk", "verified_neumann_fallback"}
    assert len(result["u_interval_by_site"]) == 3
    assert (bare, screened) == (clean_bare, clean_screened)
    assert result["u_interval_by_site"] == clean_result["u_interval_by_site"]


def test_policy_driven_repeatability_math_has_no_material_or_expected_u_assumption():
    first = repeatability_envelope("3.14159", ["3.143", "3.139", "3.147"])
    second = repeatability_envelope("-8.25", ["-8.20", "-8.31", "-8.24"])
    assert first["max_abs_delta"] == Fraction("0.00541")
    assert first["lower"] == Fraction("3.13618")
    assert first["upper"] == Fraction("3.14700")
    assert second["max_abs_delta"] == Fraction("0.06")
    with pytest.raises(CertificationError, match="at least one replica"):
        repeatability_envelope("1.0", [])


def test_decision_engine_has_no_benchmark_material_or_u_literals():
    root = Path(__file__).resolve().parents[2]
    decision_modules = (
        "src/hubbardflow/domain/u_certification.py",
        "src/hubbardflow/domain/u_repeatability.py",
        "src/hubbardflow/domain/lr_analysis_v2.py",
        "src/hubbardflow/execution/u_certification_node.py",
        "src/hubbardflow/execution/u_release_gate.py",
        "src/hubbardflow/execution/campaign_runner.py",
        "src/hubbardflow/execution/campaign_v2.py",
        "production_benchmarks/slurm_runner.py",
    )
    forbidden = re.compile(
        r"\b(?:NiO|MnO|FeO|CoO|NiLR\d*|MnLR\d*|FeLR\d*|CoLR\d*)\b|"
        r"\b(?:6\.861874|11\.117477|5\.638282|5\.818030)\b"
    )
    for relative in decision_modules:
        tree = ast.parse((root / relative).read_text(encoding="utf-8"), filename=relative)
        docstring_nodes = set()
        for parent in ast.walk(tree):
            if isinstance(parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and parent.body:
                first = parent.body[0]
                if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    docstring_nodes.add(id(first.value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in docstring_nodes:
                    continue
                assert forbidden.search(node.value) is None, f"benchmark literal in decision module {relative}"
