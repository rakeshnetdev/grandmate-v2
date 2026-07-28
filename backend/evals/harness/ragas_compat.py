"""Workaround for a broken upstream `ragas` dependency (Phase 7).

`ragas` (even pinned below 0.4, see `pyproject.toml`'s comment) unconditionally imports
`langchain_community.chat_models.vertexai` at package load time — a module that no
longer exists in current `langchain-community` releases (it moved to the separate
`langchain-google-vertexai` package upstream; see
https://github.com/vibrantlabsai/ragas/issues/2741 and #2745). This harness only uses
`ragas`'s non-LLM context precision/recall metrics and never touches Vertex AI at all,
so the fix is a harmless stub, not a real dependency on Google's SDK.

**Call `ensure_ragas_importable()` before any `import ragas` in this process, as its own
statement — not just an import of this module.** Importing a submodule of a package
(`ragas.metrics`) still executes `ragas/__init__.py` first, so there is no dodging this
by importing something "deeper." And a bare `import ragas_compat` for its side effect is
fragile here specifically: an isort/ruff autofix pass is free to reorder a plain import
statement relative to other imports (it reordered exactly this one below the `ragas`
imports it was meant to precede, the first time this was written as a bare import) — a
function *call* is not an import statement, so it cannot be reordered out from under the
`# noqa: E402` imports that follow it.
"""

from __future__ import annotations

import sys
import types


def ensure_ragas_importable() -> None:
    if "langchain_community.chat_models.vertexai" in sys.modules:
        return

    stub = types.ModuleType("langchain_community.chat_models.vertexai")

    class _StubChatVertexAI:  # pragma: no cover - never actually instantiated
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError(
                "ChatVertexAI is a compatibility stub (see ragas_compat.py) and was "
                "never meant to be instantiated — this harness does not use Vertex AI."
            )

    stub.ChatVertexAI = _StubChatVertexAI  # type: ignore[attr-defined]
    sys.modules["langchain_community.chat_models.vertexai"] = stub


__all__ = ["ensure_ragas_importable"]
