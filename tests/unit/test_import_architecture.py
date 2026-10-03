"""Pin existing import debt while preventing new layer leaks and cycles.

All runtime imports are inspected, including imports inside functions. Existing
exceptions are explicit Phase 3 debt and must disappear when the debt is fixed.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from hubbardflow.domain.scf_ladder_models import ScfLadderError
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.execution.campaign_v2 import CampaignV2Error
from hubbardflow.execution.campaign_v2 import resolve_fdf_includes as campaign_resolve
from hubbardflow.siesta_backend.fdf_includes import FdfIncludeError, resolve_fdf_includes
from hubbardflow.siesta_backend.fdf_model import FdfErrorCode, FdfModelError, parse_effective_fdf
from hubbardflow.siesta_backend.scf_ladder_inputs import bind_ladder_input

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "hubbardflow"

ALLOWLIST: frozenset[str] = frozenset(
    {
        "backend: hubbardflow.siesta_backend.command_factory -> hubbardflow.execution.execution_profile",  # phase 3
        "backend: hubbardflow.siesta_backend.command_factory -> hubbardflow.execution.hydra_launcher",  # phase 3
        "backend: hubbardflow.siesta_backend.command_factory -> hubbardflow.execution.lr_dag",  # phase 3
        "backend: hubbardflow.siesta_backend.command_factory -> hubbardflow.execution.runtime_adapters",  # phase 3
        "backend: hubbardflow.siesta_backend.output_validator -> hubbardflow.execution.dag_contract",  # phase 3
        "backend: hubbardflow.siesta_backend.output_validator -> hubbardflow.execution.generic_executor",  # phase 3
        "backend: hubbardflow.siesta_backend.output_validator -> hubbardflow.execution.lr_dag",  # phase 3
        "backend: hubbardflow.siesta_backend.output_validator -> hubbardflow.execution.runtime_adapters",  # phase 3
        "backend: hubbardflow.siesta_backend.production_runtime -> hubbardflow.execution.execution_profile",  # phase 3
        "backend: hubbardflow.siesta_backend.production_runtime -> hubbardflow.execution.runtime_adapters",  # phase 3
        "cycle: hubbardflow.execution.campaign_split -> hubbardflow.execution.product_paths",  # phase 3
        "cycle: hubbardflow.execution.product_models -> hubbardflow.execution.campaign_split",  # phase 3
        "cycle: hubbardflow.execution.product_paths -> hubbardflow.execution.product_models",  # phase 3
        "cycle: hubbardflow.execution.source_evidence -> hubbardflow.execution.u_release_gate",  # phase 3
        "cycle: hubbardflow.execution.u_certification_node -> hubbardflow.execution.source_evidence",  # phase 3
        "cycle: hubbardflow.execution.u_certification_node -> hubbardflow.execution.u_release_gate",  # phase 3
        "cycle: hubbardflow.execution.u_release_gate -> hubbardflow.execution.u_certification_node",  # phase 3
        "domain: hubbardflow.domain.symmetry_reduction -> symmetry_reduction_proposal",  # phase 3
        "private: hubbardflow.domain.fdebq_models -> hubbardflow.domain.response_budget_models:_Record",  # phase 3
        "private: hubbardflow.domain.response_budget_moments -> hubbardflow.domain.response_budget_models:_Record",  # phase 3
        "private: hubbardflow.domain.response_error_budget -> hubbardflow.domain.response_budget_models:_derived_finite",  # phase 3
        "private: hubbardflow.domain.response_shadow -> hubbardflow.domain.response_budget_models:_Record",  # phase 3
        "private: hubbardflow.domain.scf_budget_adapter -> hubbardflow.domain.fdebq_models:_RoundRecord",  # phase 3
        "private: hubbardflow.domain.scf_budget_adapter -> hubbardflow.domain.response_budget_models:_derived_finite",  # phase 3
        "private: hubbardflow.domain.scf_ladder -> hubbardflow.domain.response_budget_models:_derived_finite",  # phase 3
        "private: hubbardflow.domain.scf_ladder_models -> hubbardflow.domain.response_budget_models:_Record",  # phase 3
        "private: hubbardflow.domain.scf_validation -> hubbardflow.domain.scf_ladder_models:_ScfRecord",  # phase 3
        "private: hubbardflow.domain.symmetry_operations -> hubbardflow.domain.symmetry_geometry:_k_invariant",  # phase 3
        "private: hubbardflow.domain.symmetry_operations -> hubbardflow.domain.symmetry_geometry:_lattice_compatible",  # phase 3
        "private: hubbardflow.execution.campaign_plan -> hubbardflow.domain.lr_analysis_v2:_fit_method",  # phase 3
        "private: hubbardflow.execution.campaign_runner -> hubbardflow.domain.response_grid_reproducibility:_execution_attempt",  # phase 3
        "private: hubbardflow.execution.u_certification_node -> hubbardflow.execution.source_evidence:_safe_relative_file",  # phase 3
        "private: hubbardflow.execution.wsl_campaign_init -> hubbardflow.execution.campaign_v2:_safe_relative",  # phase 3
        "private: hubbardflow.siesta_backend.command_factory -> hubbardflow.siesta_backend.backend_admission_plugin:_is_campaign_contract_admission",  # phase 3
        "private: hubbardflow.siesta_backend.coverage_reference -> hubbardflow.siesta_backend.fdf_model:_blocks",  # phase 3
        "private: hubbardflow.siesta_backend.coverage_reference -> hubbardflow.siesta_backend.fdf_model:_one",  # phase 3
        "private: hubbardflow.siesta_backend.coverage_reference -> hubbardflow.siesta_backend.reference_magnetic_evidence:_is_explicitly_nonpolarized",  # phase 3
        "private: hubbardflow.siesta_backend.output_validator -> hubbardflow.siesta_backend.backend_admission_plugin:_is_campaign_contract_admission",  # phase 3
        "private: hubbardflow.siesta_backend.production_runtime -> hubbardflow.siesta_backend.backend_admission_plugin:_is_campaign_contract_admission",  # phase 3
        "private: hubbardflow.siesta_backend.scf_ladder_inputs -> hubbardflow.domain.response_budget_models:_Record",  # phase 3
        "private: hubbardflow.siesta_backend.scf_ladder_inputs -> hubbardflow.siesta_backend.fdf_model:_directive_rows",  # phase 3
        "private: hubbardflow.siesta_backend.scf_ladder_inputs -> hubbardflow.siesta_backend.fdf_model:_one",  # phase 3
        "private: hubbardflow.siesta_backend.symmetry_materializer -> hubbardflow.siesta_backend.backend_admission_plugin:_is_campaign_contract_admission",  # phase 3
        "reporting: hubbardflow.reporting.product_report -> hubbardflow.execution.product_models",  # phase 3
    }
)


@dataclass(frozen=True)
class ImportEdge:
    source: str
    target: str
    name: str | None = None


class RuntimeImports(ast.NodeVisitor):
    """Resolve static imports without discarding function bodies or else paths."""

    def __init__(self, source: str, modules: frozenset[str], *, package: bool = False) -> None:
        self.source = source
        self.modules = modules
        self.package = source if package else source.rpartition(".")[0]
        self.edges: set[ImportEdge] = set()
        self.type_checking_names = {"TYPE_CHECKING"}
        self.typing_names = {"typing"}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.edges.add(ImportEdge(self.source, alias.name))
            if alias.name == "typing":
                self.typing_names.add(alias.asname or alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            prefix = self.package.split(".")
            keep = len(prefix) - node.level + 1
            base = ".".join(prefix[:keep])
            if node.module:
                base += "." + node.module
        else:
            base = node.module or ""
        for alias in node.names:
            target = f"{base}.{alias.name}"
            if target not in self.modules:
                target = base
            self.edges.add(ImportEdge(self.source, target, alias.name))
            if base == "typing" and alias.name == "TYPE_CHECKING":
                self.type_checking_names.add(alias.asname or alias.name)

    def _type_checking_value(self, node: ast.expr) -> bool | None:
        if isinstance(node, ast.Name) and node.id in self.type_checking_names:
            return False
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in self.typing_names
            and node.attr == "TYPE_CHECKING"
        ):
            return False
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = self._type_checking_value(node.operand)
            return None if value is None else not value
        if isinstance(node, ast.BoolOp):
            values = [self._type_checking_value(value) for value in node.values]
            if isinstance(node.op, ast.And) and False in values:
                return False
            if isinstance(node.op, ast.Or) and True in values:
                return True
        return None

    def visit_If(self, node: ast.If) -> None:
        value = self._type_checking_value(node.test)
        if value is not False:
            for child in node.body:
                self.visit(child)
        if value is not True:
            for child in node.orelse:
                self.visit(child)


def import_graph(sources: Mapping[str, str], packages: frozenset[str] = frozenset()) -> set[ImportEdge]:
    modules = frozenset(sources)
    edges: set[ImportEdge] = set()
    for source, text in sorted(sources.items()):
        visitor = RuntimeImports(source, modules, package=source in packages)
        visitor.visit(ast.parse(text, filename=source))
        edges.update(visitor.edges)
    return edges


def _layer(module: str) -> str:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 and parts[0] == "hubbardflow" else ""


def architecture_violations(edges: set[ImportEdge]) -> set[str]:
    violations: set[str] = set()
    graph: dict[str, set[str]] = {}
    for edge in sorted(edges, key=lambda edge: (edge.source, edge.target, edge.name or "")):
        source_layer, target_layer = _layer(edge.source), _layer(edge.target)
        top = edge.target.split(".")[0]
        allowed_domain = (
            target_layer == "domain" or top in sys.stdlib_module_names or top in {"__future__", "numpy"}
        )
        if source_layer == "domain" and not allowed_domain:
            violations.add(f"domain: {edge.source} -> {edge.target}")
        if source_layer == "siesta_backend" and target_layer in {
            "execution",
            "reporting",
            "cli",
            "product_cli",
        }:
            violations.add(f"backend: {edge.source} -> {edge.target}")
        if source_layer == "reporting" and target_layer == "execution":
            violations.add(f"reporting: {edge.source} -> {edge.target}")
        if edge.source != edge.target and edge.name and edge.name.startswith("_"):
            violations.add(f"private: {edge.source} -> {edge.target}:{edge.name}")
        if edge.source != edge.target and any(
            part.startswith("_") and part != "__future__" for part in edge.target.split(".")
        ):
            violations.add(f"private-module: {edge.source} -> {edge.target}")
        if edge.target.startswith("hubbardflow.") and edge.source != edge.target:
            graph.setdefault(edge.source, set()).add(edge.target)

    def reaches(source: str, target: str) -> bool:
        pending = [source]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current not in seen:
                seen.add(current)
                pending.extend(sorted(graph.get(current, set()) - seen))
        return False

    for source, targets in sorted(graph.items()):
        for target in sorted(targets):
            if reaches(target, source):
                violations.add(f"cycle: {source} -> {target}")
    return violations


def assert_allowlist(violations: set[str], allowlist: frozenset[str]) -> None:
    new = sorted(violations - allowlist)
    stale = sorted(allowlist - violations)
    assert not new and not stale, f"New architecture violations: {new}\nStale allowlist entries: {stale}"


def test_package_import_architecture() -> None:
    sources: dict[str, str] = {}
    packages: set[str] = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).with_suffix("")
        parts = relative.parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        module = ".".join(("hubbardflow", *parts))
        sources[module] = path.read_text(encoding="utf-8-sig")
        if path.name == "__init__.py":
            packages.add(module)
    assert_allowlist(architecture_violations(import_graph(sources, frozenset(packages))), ALLOWLIST)


def test_graph_includes_function_imports_and_excludes_type_checking() -> None:
    sources = {
        "hubbardflow.domain.a": """from typing import TYPE_CHECKING as TC
import typing as tp
if TC:
    import hubbardflow.execution.hidden
if tp.TYPE_CHECKING:
    import hubbardflow.execution.also_hidden
if not TC:
    def later():
        from .b import _private
else:
    import hubbardflow.execution.hidden_else
""",
        "hubbardflow.domain.b": "def later():\n    from .a import public\n",
    }
    edges = import_graph(sources)
    assert not any("hidden" in edge.target for edge in edges)
    assert ImportEdge("hubbardflow.domain.a", "hubbardflow.domain.b", "_private") in edges
    violations = architecture_violations(edges)
    assert "private: hubbardflow.domain.a -> hubbardflow.domain.b:_private" in violations
    assert "cycle: hubbardflow.domain.a -> hubbardflow.domain.b" in violations
    assert "cycle: hubbardflow.domain.b -> hubbardflow.domain.a" in violations


def test_layer_rules_and_allowlist_reject_new_and_stale_debt() -> None:
    edges = {
        ImportEdge("hubbardflow.domain.a", "numpy.linalg"),
        ImportEdge("hubbardflow.domain.a", "pathlib"),
        ImportEdge("hubbardflow.domain.a", "spglib"),
        ImportEdge("hubbardflow.siesta_backend.a", "hubbardflow.execution.b"),
        ImportEdge("hubbardflow.reporting.a", "hubbardflow.execution.b"),
    }
    violations = architecture_violations(edges)
    assert violations == {
        "domain: hubbardflow.domain.a -> spglib",
        "backend: hubbardflow.siesta_backend.a -> hubbardflow.execution.b",
        "reporting: hubbardflow.reporting.a -> hubbardflow.execution.b",
    }
    assert_allowlist(violations, frozenset(violations))
    with pytest.raises(AssertionError, match="New architecture violations"):
        assert_allowlist(violations, frozenset())
    with pytest.raises(AssertionError, match="Stale allowlist entries"):
        assert_allowlist(set(), frozenset(violations))


def test_private_module_imports_are_rejected_even_with_public_aliases() -> None:
    sources = {
        "hubbardflow.domain.a": """from __future__ import annotations
import hubbardflow.domain._private as public_alias
def later():
    from hubbardflow.domain._nested.public import exported
""",
    }
    assert architecture_violations(import_graph(sources)) == {
        "private-module: hubbardflow.domain.a -> hubbardflow.domain._private",
        "private-module: hubbardflow.domain.a -> hubbardflow.domain._nested.public",
    }


def test_include_expansion_preserves_bytes_and_dependency_order(tmp_path: Path) -> None:
    child = tmp_path / "child.fdf"
    leaf = tmp_path / "leaf.fdf"
    source = tmp_path / "source.fdf"
    leaf.write_bytes(b"leaf\r\n")
    child.write_text("child\n%include leaf.fdf\n", encoding="utf-8")
    source.write_text("start\n%include child.fdf\n#include leaf.fdf\nend\n", encoding="utf-8")
    expected = ("start\nchild\nleaf\n\n\nleaf\n\nend\n", [child.resolve(), leaf.resolve()])
    assert resolve_fdf_includes(source) == expected
    assert campaign_resolve(source) == expected


@pytest.mark.parametrize("text", ["%include source.fdf\n", "%include\n"])
def test_include_errors_keep_each_boundary_contract(tmp_path: Path, text: str) -> None:
    source = tmp_path / "source.fdf"
    source.write_text(text, encoding="utf-8")
    with pytest.raises(FdfIncludeError) as backend:
        resolve_fdf_includes(source)
    with pytest.raises(CampaignV2Error) as campaign:
        campaign_resolve(source)
    assert str(campaign.value) == str(backend.value)
    assert isinstance(campaign.value.__cause__, FdfIncludeError)
    with pytest.raises(FdfModelError) as model:
        parse_effective_fdf(source)
    assert model.value.code is FdfErrorCode.UNSUPPORTED_SYNTAX
    assert isinstance(model.value.__cause__, FdfIncludeError)
    with pytest.raises(ScfLadderError, match="NOT_ESTABLISHED"):
        bind_ladder_input(source, "NiLR0", ResponseMode.BARE, 0.02)


def test_missing_include_keeps_historical_filesystem_error(tmp_path: Path) -> None:
    source = tmp_path / "source.fdf"
    source.write_text("%include missing.fdf\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        resolve_fdf_includes(source)
    with pytest.raises(FileNotFoundError):
        campaign_resolve(source)
    with pytest.raises(FdfModelError) as model:
        parse_effective_fdf(source)
    assert model.value.code is FdfErrorCode.UNSUPPORTED_SYNTAX
    assert isinstance(model.value.__cause__, FileNotFoundError)
    with pytest.raises(ScfLadderError, match="NOT_ESTABLISHED"):
        bind_ladder_input(source, "NiLR0", ResponseMode.BARE, 0.02)
