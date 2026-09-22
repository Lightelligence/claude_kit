---
name: soc-integrate-bazel
description: Project Bazel 集成验证工具。验证 WORKSPACE, BUILD, ip_defs.bzl; 管理模块依赖和 Vendor IP。
---

# SoC Integrate Bazel

使用此 MCP 管理和验证 Project 的 Bazel 集成。禁止直接调用 `bazel query` 或 `bazel build`。

## 工具

| 工具 | 说明 |
|---|---|
| `validate_workspace()` | 验证 WORKSPACE 文件语法和完整性 |
| `validate_ip_defs()` | 验证 hw/vendor/rtl/ip_defs.bzl |
| `check_module_deps(module)` | 检查模块依赖图 |
| `list_rtl_targets()` | 列出所有 RTL Bazel 目标 |
| `check_build_graph()` | 检查整个构建图一致性 |
| `check_vendor_ip_paths()` | 检查 Vendor IP 路径是否存在 |
| `add_vendor_ip_entry(ip_name, ip_path, build_file)` | 生成新 Vendor IP 条目 |

## Claude Code 对话示例

以下是英文 prompts，不是可运行的 Python；参数以当前注册 schema 为准。

```text
Use the registered soc-integrate-bazel tools to validate WORKSPACE and inspect
dependencies for module <module>. Report missing vendor IP paths if relevant.
Do not edit BUILD files or execute a build.
```

```text
Generate a vendor IP entry for name <name>, approved path <path> and
build-file label <label> using the registered add_vendor_ip_entry tool.
Show the returned snippet for review; do not apply or publish it.
```
