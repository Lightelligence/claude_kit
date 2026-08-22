"""Optional project-side adapter template for claude_kit.

Keep project names, target aliases and tool-specific behavior here. Keep
generic roles, protocol rules and evidence semantics in claude_kit itself.
"""

from typing import Any


def resolve_target(name: str) -> str:
    """Map a short project target name to the project's real target."""
    return name


def resolve_test(selector: str) -> str:
    """Map a short test selector to the project's real test selection."""
    return selector


def resolve_vip(protocol: str) -> dict[str, Any]:
    """Return project-specific interface and VIP mapping for a protocol."""
    return {"protocol": protocol}


def collect_artifacts(run_id: str) -> list[str]:
    """Return project-relative artifact paths for a completed run."""
    return []
