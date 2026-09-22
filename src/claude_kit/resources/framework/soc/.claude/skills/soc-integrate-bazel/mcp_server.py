#!/usr/bin/env python3
"""
Project Bazel 集成 MCP Server

验证 BUILD 文件、WORKSPACE、ip_defs.bzl 的一致性。
帮助 soc-integrator 管理模块依赖和 Vendor IP 集成。
"""

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("WARNING: mcp package not available, running in CLI mode", file=sys.stderr)


# 脚本路径: <PROJECT_ROOT>/.claude/skills/soc-integrate-bazel/mcp_server.py
# parents[3] = PROJECT_ROOT
def _find_project_root() -> Path:
    for parent in (Path.cwd(), *Path.cwd().parents):
        if (parent / "WORKSPACE").is_file() or (parent / "WORKSPACE.bazel").is_file():
            return parent
    raise RuntimeError("Project WORKSPACE root was not found")


PROJECT_ROOT = _find_project_root()

if MCP_AVAILABLE:
    mcp = FastMCP(
        name="soc-integrate-bazel",
        instructions=("Project Bazel 集成工具。"
                      "验证 WORKSPACE, BUILD, ip_defs.bzl; 管理模块依赖和 Vendor IP 集成。"),
    )
else:
    mcp = None


def _run_bazel(args: List[str], capture: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    cmd = ["bazel"] + args
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT), timeout=timeout, capture_output=capture, text=True)


def _repository_issue(line: int, field: str, reason: str) -> Dict[str, Any]:
    return {
        "line": line,
        "field": field,
        "reason": reason,
        "message": f"{field} is {reason}",
    }


def _static_string(node: Optional[ast.AST]) -> Optional[str]:
    """Return only a literal string; never evaluate Starlark expressions."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    legacy_str = getattr(ast, "Str", None)
    if legacy_str is not None and isinstance(node, legacy_str):
        return node.s
    return None


def _extract_native_local_repositories(
    content: str,
    source: Path,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract targeted repository calls without attempting full Starlark validation."""
    try:
        tree = ast.parse(content, filename=str(source))
    except SyntaxError as exc:
        return [], [{
            "line": exc.lineno or 0,
            "field": "file",
            "reason": "unsupported_syntax",
            "message": str(exc),
        }]

    records = []
    unresolved = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "native"
            and node.func.attr == "new_local_repository"
        ):
            continue

        line = getattr(node, "lineno", 0)
        call_issues = []
        values = {}
        if node.args:
            call_issues.append(_repository_issue(line, "positional_arguments", "unsupported"))

        for keyword in node.keywords:
            if keyword.arg is None:
                call_issues.append(_repository_issue(line, "**kwargs", "dynamic"))
            elif keyword.arg in values:
                call_issues.append(_repository_issue(line, keyword.arg, "duplicate"))
            else:
                values[keyword.arg] = keyword.value

        fields = {}
        for field in ("name", "path"):
            if field not in values:
                fields[field] = None
                call_issues.append(_repository_issue(line, field, "missing"))
                continue
            fields[field] = _static_string(values[field])
            if fields[field] is None:
                call_issues.append(_repository_issue(line, field, "dynamic"))

        record = {
            "name": fields["name"],
            "path": fields["path"],
            "line": line,
            "unresolved": call_issues,
        }
        records.append(record)
        unresolved.extend(call_issues)

    records.sort(key=lambda record: record["line"])
    unresolved.sort(key=lambda issue: (issue["line"], issue["field"]))
    return records, unresolved


def _resolve_vendor_path(ip_path: str) -> Path:
    candidate = Path(ip_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


if MCP_AVAILABLE:

    @mcp.tool()
    def validate_workspace() -> Dict[str, Any]:
        """验证 WORKSPACE 文件的语法和完整性"""
        workspace_file = PROJECT_ROOT / "WORKSPACE"
        if not workspace_file.exists():
            return {"status": "FAIL", "error": "WORKSPACE file not found"}

        content = workspace_file.read_text()
        errors = []
        if "load(" not in content:
            errors.append("WORKSPACE missing load() statements")
        if "workspace(" not in content:
            errors.append("WORKSPACE missing workspace() definition")

        return {
            "status": "PASS" if not errors else "FAIL",
            "errors": errors,
            "file": str(workspace_file),
        }

    @mcp.tool()
    def validate_ip_defs() -> Dict[str, Any]:
        """验证 hw/vendor/rtl/ip_defs.bzl 的 repository 定义"""
        ip_defs = PROJECT_ROOT / "hw/vendor/rtl/ip_defs.bzl"
        if not ip_defs.exists():
            return {"status": "FAIL", "error": "ip_defs.bzl not found"}

        content = ip_defs.read_text()
        records, unresolved = _extract_native_local_repositories(content, ip_defs)
        return {
            "status": "FAIL" if unresolved else "PASS",
            "repositories": len(records),
            "ip_names": [record["name"] for record in records if record["name"] is not None],
            "unresolved": unresolved,
            "file": str(ip_defs),
        }

    @mcp.tool()
    def check_module_deps(module: str) -> Dict[str, Any]:
        """
        验证模块的所有依赖都能正确链接

        Args:
            module: 模块名 (如 "eic")
        """
        target = f"//hw/rtl/{module}:top"
        result = _run_bazel(["query", f"deps({target})"])

        if result.returncode != 0:
            return {"status": "FAIL", "error": result.stderr, "module": module}

        deps = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return {
            "status": "PASS",
            "module": module,
            "target": target,
            "dependency_count": len(deps),
            "dependencies": deps[:30],
        }

    @mcp.tool()
    def list_rtl_targets() -> Dict[str, list]:
        """列出所有 RTL 模块的 Bazel 目标"""
        result = _run_bazel(["query", "kind(verilog_rtl_library, //hw/rtl/...)"])

        if result.returncode != 0:
            return {"error": result.stderr, "targets": []}

        targets = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return {"targets": targets}

    @mcp.tool()
    def check_build_graph() -> Dict[str, Any]:
        """检查 Bazel 构建图的一致性"""
        result = _run_bazel(["query", "//hw/..."], timeout=300)

        if result.returncode != 0:
            return {"status": "FAIL", "error": result.stderr[:500]}

        all_targets = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return {
            "status": "PASS",
            "total_targets": len(all_targets),
            "sample": all_targets[:20],
        }

    @mcp.tool()
    def check_vendor_ip_paths() -> Dict[str, Any]:
        """检查 ip_defs.bzl 中定义的 Vendor IP 路径是否存在"""
        ip_defs = PROJECT_ROOT / "hw/vendor/rtl/ip_defs.bzl"
        if not ip_defs.exists():
            return {"status": "FAIL", "error": "ip_defs.bzl not found"}

        content = ip_defs.read_text()
        records, unresolved = _extract_native_local_repositories(content, ip_defs)
        results = []
        for record in records:
            result = {
                "ip": record["name"],
                "path": record["path"],
                "exists": None,
            }
            if record["unresolved"]:
                result["status"] = "UNRESOLVED"
                result["issues"] = record["unresolved"]
            else:
                result["exists"] = _resolve_vendor_path(record["path"]).exists()
            results.append(result)

        missing = [result for result in results if result["exists"] is False]
        return {
            "status": "FAIL" if missing or unresolved else "PASS",
            "total_ips": len(results),
            "missing_ips": missing,
            "unresolved": unresolved,
            "all_ips": results,
        }

    @mcp.tool()
    def add_vendor_ip_entry(
        ip_name: str,
        ip_path: str,
        build_file: str,
    ) -> Dict[str, Any]:
        """
        生成新的 Vendor IP 的 ip_defs.bzl 条目 (不自动写入)

        Args:
            ip_name: IP 名称 (如 "my_new_ip")
            ip_path: IP 源码绝对路径
            build_file: Bazel BUILD 文件路径 (如 "//hw/vendor/rtl:BUILD.my_new_ip")
        """
        entry = f'''
    native.new_local_repository(
        name = "{ip_name}",
        path = "{ip_path}",
        build_file = "{build_file}",
    )
'''
        return {
            "status": "GENERATED",
            "ip_name": ip_name,
            "entry": entry,
            "message": f"Add this entry to load_ip() in hw/vendor/rtl/ip_defs.bzl",
        }


def cli_main():
    """CLI 模式"""
    import argparse
    parser = argparse.ArgumentParser(description="Project Bazel Integrate MCP (CLI mode)")
    parser.add_argument("method", nargs="?", help="Method to call")
    args = parser.parse_args()

    if not args.method:
        parser.print_help()
        return

    if args.method == "validate-workspace":
        workspace_file = PROJECT_ROOT / "WORKSPACE"
        if workspace_file.exists():
            print(f"✓ WORKSPACE found: {workspace_file}")
        else:
            print(f"✗ WORKSPACE not found")

    elif args.method == "validate-ip-defs":
        ip_defs = PROJECT_ROOT / "hw/vendor/rtl/ip_defs.bzl"
        if ip_defs.exists():
            content = ip_defs.read_text()
            records, unresolved = _extract_native_local_repositories(content, ip_defs)
            if unresolved:
                print(
                    f"✗ ip_defs.bzl parsed: {len(records)} repositories; "
                    f"{len(unresolved)} unresolved values"
                )
                for issue in unresolved:
                    print(f"  {issue['field']}: {issue['reason']} (line {issue['line']})")
            else:
                print(f"✓ ip_defs.bzl found: {len(records)} repositories defined")
        else:
            print(f"✗ ip_defs.bzl not found")

    elif args.method == "list-rtl-targets":
        result = _run_bazel(["query", "kind(verilog_rtl_library, //hw/rtl/...)"])
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    print(line.strip())

    elif args.method == "check-vendor-paths":
        ip_defs = PROJECT_ROOT / "hw/vendor/rtl/ip_defs.bzl"
        if not ip_defs.exists():
            print("✗ ip_defs.bzl not found")
            return
        content = ip_defs.read_text()
        records, unresolved = _extract_native_local_repositories(content, ip_defs)
        for record in records:
            if record["unresolved"]:
                print(
                    f"? {record['name'] or '<unresolved>'}: "
                    f"{record['path'] or '<unresolved>'} "
                    f"(unresolved: {len(record['unresolved'])})"
                )
                continue
            exists = _resolve_vendor_path(record["path"]).exists()
            status = "✓" if exists else "✗"
            print(f"{status} {record['name']}: {record['path']}")
        if unresolved:
            print(f"✗ {len(unresolved)} unresolved repository values")

    else:
        print(f"Unknown method: {args.method}")
        print("Available: validate-workspace, validate-ip-defs, list-rtl-targets, check-vendor-paths")


def main():
    if MCP_AVAILABLE:
        mcp.run()
    else:
        cli_main()


if __name__ == "__main__":
    main()
