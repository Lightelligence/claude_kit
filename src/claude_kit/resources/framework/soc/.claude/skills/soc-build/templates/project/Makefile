# SoC unified build entry.

PROJECT_ROOT := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))
MODULE       ?= chip/top
MODULE_DIR   := $(PROJECT_ROOT)/$(MODULE)
TARGET       ?= help

export PROJECT_ROOT

include $(PROJECT_ROOT)/scripts/config.mk

.DEFAULT_GOAL := help

.PHONY: help setup check-env check-repo list-modules print-config module \
        flist validate-flist comp sim run test regress report coverage \
        coverage-regress coverage-report verdi lint cdc syn formal formal-upf clp-upf \
        clean debugclean deepclean \
        agent-sync agent-check agent-setup mcp-setup

help:
	@echo "SoC Build System"
	@echo "=========================="
	@echo "  make list-modules                 列出可构建模块"
	@echo "  make check-env                    检查本机工具链"
	@echo "  make check-repo                   检查隐私路径和 license 泄漏"
	@echo "  make agent-setup                  准备 Claude Code 的 skill/MCP 开发环境"
	@echo "  make agent-sync                   从 .claude 同步 Claude Code 配置"
	@echo "  make agent-check                  校验 Claude Code/MCP/loop 契约无漂移"
	@echo "  make <target> [MODULE=<path>]     构建指定模块（默认 chip/top）"
	@echo "  make module MODULE=<path> TARGET=<target>"
	@echo ""
	@echo "Targets: flist validate-flist comp sim test regress report coverage"
	@echo "         coverage-regress verdi lint cdc syn formal formal-upf clp-upf"
	@echo "         clean debugclean deepclean print-config"
	@echo "Example: make lint MODULE=ip/digital/uart"
	@echo "         make comp MODULE=chip/top SIMULATOR=verilator"

setup check-env:
	@bash $(PROJECT_ROOT)/scripts/setup.sh --check

check-repo:
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/check_repo_hygiene.py --root $(PROJECT_ROOT)

# --- Agent / skill / MCP development environment ----------------------------
# Canonical sources live under .claude/. Generated adapters:
#   Claude Code: .claude/agents|skills (native directories) + .mcp.json
agent-sync:
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_loop_state_entrypoints.py
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_loop_contracts.py --check
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_agent_profiles.py --write
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_mcp_configs.py --write
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_mcp_runtime.py --write
	@mkdir -p $(PROJECT_ROOT)/tmp/worktrees
	@mkdir -p $(PROJECT_ROOT)/.claude/agents
	@mkdir -p $(PROJECT_ROOT)/.claude/skills
	@echo "[AGENT] synced profiles, MCP configs, Claude directories, tmp/worktrees"

mcp-setup:
	@bash $(PROJECT_ROOT)/.claude/scripts/setup_mcp_env.sh

agent-setup: agent-sync mcp-setup
	@echo "[AGENT] environment ready"
	@echo "  Worktrees: $(PROJECT_ROOT)/tmp/worktrees"
	@echo "  Loop packet: python3 .claude/scripts/loop_context.py . --format text"

agent-check:
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_loop_state_entrypoints.py --check
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_loop_contracts.py --check
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_agent_profiles.py --check
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_mcp_configs.py --check
	@$(PYTHON_RUN) $(PROJECT_ROOT)/scripts/sync_mcp_runtime.py --check
	@test -d $(PROJECT_ROOT)/.claude/agents && test -d $(PROJECT_ROOT)/.claude/skills
	@echo "[AGENT] all checks passed"

list-modules:
	@find $(PROJECT_ROOT)/chip $(PROJECT_ROOT)/ip -mindepth 2 -maxdepth 3 \
		-name Makefile ! -path '*/de/Makefile' ! -path '*/dv/Makefile' \
		-printf '%h\n' | sed 's|^$(PROJECT_ROOT)/||' | sort

print-config:
	@echo "PROJECT_ROOT=$(PROJECT_ROOT)"
	@echo "MODULE=$(MODULE)"
	@echo "SIMULATOR=$(or $(SIMULATOR),verilator)"
	@echo "LINT_TOOL=$(or $(LINT_TOOL),verilator)"

module:
	@test -f "$(MODULE_DIR)/Makefile" || { \
		echo "[ERROR] Invalid MODULE '$(MODULE)': module Makefile not found"; exit 2; \
	}
	@$(MAKE) --no-print-directory -C "$(MODULE_DIR)" "$(TARGET)"

flist validate-flist comp sim run test regress report coverage \
coverage-regress coverage-report verdi lint cdc syn formal formal-upf clp-upf \
clean debugclean deepclean:
	@$(MAKE) --no-print-directory module TARGET=$@
