"""Architectural boundary enforcement (ADR-0003).

`claude.md` rule 8 requires deterministic chess analysis to stay separate from LLM
explanation logic. That rule is easy to agree with and easy to erode one convenient
import at a time, so it is checked mechanically rather than left to review.

The deterministic core must be reproducible and unit-testable with exact assertions. The
moment it can reach an LLM, it stops being either. The dependency points one way: the
explanation layer reads the core, never the reverse.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"

# Modules that must stay free of any LLM or orchestration dependency.
DETERMINISTIC_CORE = ("games", "analysis", "patterns", "aggregation")

# Import prefixes the deterministic core may not use.
FORBIDDEN_IN_CORE = (
    "app.integrations.llm",
    "app.orchestration",
    "app.domain.chat",
    "app.domain.reports",
    "app.mcp",
    "langgraph",
    "langchain",
    "openai",
    "anthropic",
)


def imported_modules(source: str) -> set[str]:
    """Return every module name imported by a Python source string.

    Handles both ``import x.y`` and ``from x.y import z``. Relative imports are ignored:
    they cannot cross a top-level package boundary, so they cannot violate this rule.
    """
    tree = ast.parse(source)
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)

    return modules


def violations_in(source: str, forbidden: tuple[str, ...]) -> list[str]:
    """Return the forbidden imports present in a source string."""
    return sorted(
        module
        for module in imported_modules(source)
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden)
    )


def core_python_files() -> list[Path]:
    """Every Python file currently inside a deterministic-core domain module.

    Returns an empty list until those modules land in Phases 4 to 8. The checker is in
    place first so the boundary is enforced from the first line of core code, not
    retrofitted after a violation has already been merged.
    """
    files: list[Path] = []
    for module in DETERMINISTIC_CORE:
        module_path = APP_ROOT / "domain" / module
        if module_path.exists():
            files.extend(module_path.rglob("*.py"))
    return files


# --- checker self-tests -----------------------------------------------------
# These matter: without them the suite would pass vacuously while the core modules do
# not yet exist, and a broken checker would go unnoticed until it was too late to help.


def test_checker_detects_direct_llm_import() -> None:
    source = "from app.integrations.llm.base import LLMProvider\n"

    assert violations_in(source, FORBIDDEN_IN_CORE) == ["app.integrations.llm.base"]


def test_checker_detects_orchestration_import() -> None:
    source = "import app.orchestration.graphs.skeleton\n"

    assert violations_in(source, FORBIDDEN_IN_CORE) == ["app.orchestration.graphs.skeleton"]


def test_checker_detects_vendor_sdk_import() -> None:
    source = "import openai\nimport langgraph\n"

    assert violations_in(source, FORBIDDEN_IN_CORE) == ["langgraph", "openai"]


def test_checker_allows_legitimate_core_imports() -> None:
    source = (
        "import chess\n"
        "from app.core.config import EngineSettings\n"
        "from app.domain.games import Game\n"
    )

    assert violations_in(source, FORBIDDEN_IN_CORE) == []


def test_checker_does_not_match_on_prefix_collision() -> None:
    """``app.orchestrationhelpers`` is not ``app.orchestration``."""
    source = "import app.orchestrationhelpers\n"

    assert violations_in(source, FORBIDDEN_IN_CORE) == []


def test_checker_ignores_relative_imports() -> None:
    source = "from .models import Game\nfrom ..games import Move\n"

    assert violations_in(source, FORBIDDEN_IN_CORE) == []


# --- the real boundary check ------------------------------------------------


@pytest.mark.parametrize("path", core_python_files(), ids=lambda p: str(p.relative_to(APP_ROOT)))
def test_deterministic_core_does_not_import_llm_layer(path: Path) -> None:
    """No file in the deterministic core may reach the explanation layer."""
    found = violations_in(path.read_text(), FORBIDDEN_IN_CORE)

    assert not found, (
        f"{path.relative_to(BACKEND_ROOT)} imports {found}. "
        "The deterministic chess core must not depend on LLM or orchestration code "
        "(ADR-0003). Move the logic, or invert the dependency."
    )
