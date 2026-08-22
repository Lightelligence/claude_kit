from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .core import (
    KitError,
    check_adapter,
    doctor,
    evidence_template,
    find_project_root,
    init_project,
    inspect_project,
    load_profile,
    pack_catalog,
    resolve_context,
    review_evidence_file,
    role_catalog,
    run_project_command,
    skill_catalog,
    sync_project_skills,
)


def _json_print(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _root(value: str | None) -> Path:
    return find_project_root(Path(value).resolve() if value else None)


def _project_output(root: Path, value: Path) -> Path:
    path = (value if value.is_absolute() else root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise KitError(f"Output path escapes project root: {value}") from exc
    return path


def _project_input(root: Path, value: Path, label: str) -> Path:
    path = (value if value.is_absolute() else root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise KitError(f"{label} escapes project root: {value}") from exc
    if not path.is_file():
        raise KitError(f"{label} does not exist: {value}")
    return path


def _add_project_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", help="Project root; defaults to the nearest Git root")
    parser.add_argument("--profile", help="Profile path relative to project root")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-kit",
        description="Reusable RTL/DV context, roles, packs and project checks for Claude Code",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    version = subparsers.add_parser("version", help="Show kit version")
    version.set_defaults(handler=lambda args: {"version": __version__})

    init = subparsers.add_parser("init", help="Create minimal project integration files")
    init.add_argument("--project-root", help="Project root")
    init.add_argument("--kit-path", default="third_party/claude_kit", help="Pinned kit path written into project files")
    init.add_argument("--force", action="store_true", help="Overwrite existing generated integration files")
    init.add_argument("--with-adapter", action="store_true", help="Also create an optional project adapter template")
    init.set_defaults(handler=handle_init)

    sync = subparsers.add_parser("sync", help="Materialize the kit's Claude Code skills into a project")
    sync.add_argument("--project-root", help="Project root")
    sync.add_argument("--force", action="store_true", help="Overwrite generated skill files")
    sync.set_defaults(handler=handle_sync)

    doctor_parser = subparsers.add_parser("doctor", help="Validate the project profile and permissions")
    _add_project_options(doctor_parser)
    doctor_parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    doctor_parser.add_argument("--json", action="store_true", help="Print JSON")
    doctor_parser.set_defaults(handler=handle_doctor)

    listing = subparsers.add_parser("list", help="List roles or packs")
    listing.add_argument("kind", choices=("roles", "packs", "skills"))
    listing.add_argument("--json", action="store_true", help="Print JSON")
    listing.set_defaults(handler=handle_list)

    context = subparsers.add_parser("context", help="Resolve profile, roles and packs into Claude context")
    _add_project_options(context)
    context.add_argument("--role", action="append", dest="roles", help="Role id; repeat for multiple roles")
    context.add_argument("--pack", action="append", dest="packs", help="Pack id; repeat for multiple packs")
    context.add_argument("--task", default="", help="Task text")
    context.add_argument("--task-file", type=Path, help="Read task text from a file")
    context.add_argument("--output", type=Path, help="Write Markdown context to this path")
    context.add_argument("--manifest", type=Path, help="Write JSON manifest to this path")
    context.set_defaults(handler=handle_context)

    manifest = subparsers.add_parser("manifest", help="Resolve and print the context manifest")
    _add_project_options(manifest)
    manifest.add_argument("--role", action="append", dest="roles")
    manifest.add_argument("--pack", action="append", dest="packs")
    manifest.add_argument("--task", default="")
    manifest.set_defaults(handler=handle_manifest)

    inspect = subparsers.add_parser("inspect", help="Read-only project file summary")
    _add_project_options(inspect)
    inspect.add_argument("--json", action="store_true", help="Print JSON")
    inspect.set_defaults(handler=handle_inspect)

    check = subparsers.add_parser("check", help="Run an allowlisted project command")
    _add_project_options(check)
    check.add_argument("name", help="Name under build.commands")
    check.add_argument("--confirm", action="store_true", help="Confirm commands marked confirmation=required")
    check.add_argument("--timeout", type=int, default=3600)
    check.set_defaults(handler=handle_check)

    adapter = subparsers.add_parser("adapter", help="Validate the optional project adapter")
    adapter_subparsers = adapter.add_subparsers(dest="adapter_command", required=True)
    adapter_check = adapter_subparsers.add_parser("check", help="Import and inspect the adapter contract")
    _add_project_options(adapter_check)
    adapter_check.add_argument("--json", action="store_true", help="Print JSON")
    adapter_check.set_defaults(handler=handle_adapter_check)

    mcp = subparsers.add_parser("mcp", help="Optional thin MCP bridge")
    mcp_subparsers = mcp.add_subparsers(dest="mcp_command", required=True)
    serve = mcp_subparsers.add_parser("serve", help="Serve MCP over stdio")
    _add_project_options(serve)
    serve.add_argument("--allow-exec", action="store_true", help="Expose run_check to the bridge")
    serve.set_defaults(handler=handle_mcp)

    evidence = subparsers.add_parser("evidence", help="Create or validate task evidence")
    evidence_subparsers = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_check = evidence_subparsers.add_parser("check", help="Validate an evidence JSON file")
    _add_project_options(evidence_check)
    evidence_check.add_argument("--file", required=True, type=Path, help="Project-relative evidence JSON")
    evidence_check.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    evidence_check.add_argument("--json", action="store_true", help="Print JSON")
    evidence_check.set_defaults(handler=handle_evidence_check)
    evidence_template_parser = evidence_subparsers.add_parser("template", help="Print an evidence JSON template")
    evidence_template_parser.add_argument("--output", type=Path)
    evidence_template_parser.add_argument("--project-root")
    evidence_template_parser.set_defaults(handler=handle_evidence_template)

    return parser


def handle_init(args: argparse.Namespace) -> int:
    root = _root(args.project_root)
    created = init_project(root, args.kit_path, args.force, args.with_adapter)
    _json_print({"project_root": str(root), "created": created, "status": "passed"})
    return 0


def handle_sync(args: argparse.Namespace) -> int:
    root = _root(args.project_root)
    created = sync_project_skills(root, args.force)
    _json_print({"project_root": str(root), "synced": created, "status": "passed"})
    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    result = doctor(_root(args.project_root), args.profile, args.strict)
    if args.json:
        _json_print(result)
    else:
        print(f"status: {result['status']}")
        print(f"profile: {result.get('profile') or '<none>'}")
        for issue in result["issues"]:
            print(f"{issue['level']}: {issue['message']}")
    return 0 if result["status"] == "passed" else 1


def handle_list(args: argparse.Namespace) -> int:
    if args.kind == "roles":
        result = role_catalog()
    elif args.kind == "packs":
        result = pack_catalog()
    else:
        result = skill_catalog()
    if args.json:
        _json_print(result)
    else:
        for item in result:
            summary = item.get("summary") or item.get("title") or ""
            print(f"{item['id']}\t{summary}")
    return 0


def _context_inputs(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any], str]:
    root = _root(args.project_root)
    profile_path, profile = load_profile(root, args.profile)
    task = args.task
    if getattr(args, "task_file", None):
        task = _project_input(root, args.task_file, "Task file").read_text(encoding="utf-8")
    return root, profile_path, profile, task


def handle_context(args: argparse.Namespace) -> int:
    root, profile_path, profile, task = _context_inputs(args)
    context, manifest = resolve_context(root, profile_path, profile, args.roles, args.packs, task)
    if args.output:
        path = _project_output(root, args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(context, encoding="utf-8", newline="\n")
    else:
        print(context)
    if args.manifest:
        path = _project_output(root, args.manifest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return 0


def handle_manifest(args: argparse.Namespace) -> int:
    root, profile_path, profile, task = _context_inputs(args)
    _, manifest = resolve_context(root, profile_path, profile, args.roles, args.packs, task)
    _json_print(manifest)
    return 0


def handle_inspect(args: argparse.Namespace) -> int:
    root = _root(args.project_root)
    profile = None
    try:
        _, profile = load_profile(root, args.profile)
    except KitError:
        pass
    result = inspect_project(root, profile)
    if args.json:
        _json_print(result)
    else:
        print(f"root: {result['root']}")
        print(f"scanned_files: {result['scanned_files']}")
        for name, group in result["groups"].items():
            print(f"{name}: {group['files']} files ({group['path']})")
    return 0


def handle_check(args: argparse.Namespace) -> int:
    root = _root(args.project_root)
    _, profile = load_profile(root, args.profile)
    result = run_project_command(root, profile, args.name, args.confirm, args.timeout)
    _json_print(result)
    return 0 if result["status"] == "passed" else 1


def handle_adapter_check(args: argparse.Namespace) -> int:
    root = _root(args.project_root)
    _, profile = load_profile(root, args.profile)
    result = check_adapter(root, profile)
    if args.json:
        _json_print(result)
    else:
        print(f"status: {result['status']}")
        print(f"adapter: {result.get('adapter') or '<none>'}")
        print(f"functions: {', '.join(result['functions']) or '<none>'}")
        for issue in result["issues"]:
            print(f"{issue['level']}: {issue['message']}")
    return 0 if result["status"] in ("passed", "skipped") else 1


def handle_mcp(args: argparse.Namespace) -> int:
    from .mcp_server import serve

    root = _root(args.project_root)
    serve(root, args.profile, args.allow_exec)
    return 0


def handle_evidence_check(args: argparse.Namespace) -> int:
    root = _root(args.project_root)
    _, profile = load_profile(root, args.profile)
    path = args.file
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise KitError(f"Evidence path escapes project root: {args.file}") from exc
    result = review_evidence_file(root, profile, path.as_posix(), args.strict)
    if args.json:
        _json_print(result)
    else:
        print(f"status: {result['status']}")
        print(f"file: {result['path']}")
        for issue in result["issues"]:
            print(f"{issue['level']}: {issue['message']}")
    return 0 if result["status"] == "passed" else 1


def handle_evidence_template(args: argparse.Namespace) -> int:
    content = evidence_template()
    if args.output:
        root = _root(args.project_root)
        path = _project_output(root, args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    else:
        print(content, end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
        if isinstance(result, dict):
            _json_print(result)
            return 0
        return int(result)
    except (KitError, OSError, ValueError) as exc:
        print(f"claude-kit: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
