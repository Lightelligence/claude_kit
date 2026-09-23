#!/usr/bin/env bash
# Launch the optional atlassian-dc MCP server (Confluence/Jira) without
# embedding site paths or personal credentials in the repository configuration.
#
# Each engineer configures credentials once at
#   ~/.ssh/mcp-atlassian.env
# (or points MCP_ATLASSIAN_ENV_FILE at another readable file) with:
#   export CONFLUENCE_URL=https://<confluence-host>
#   export CONFLUENCE_PERSONAL_TOKEN=<token>
#   export CONFLUENCE_SSL_VERIFY=false
#   export JIRA_URL=https://<jira-host>
#   export JIRA_PERSONAL_TOKEN=<token>
#   export JIRA_SSL_VERIFY=false
# and installs the server with:  pip install mcp-atlassian
set -Eeuo pipefail

env_file="${MCP_ATLASSIAN_ENV_FILE:-$HOME/.ssh/mcp-atlassian.env}"
if [[ ! -r "${env_file}" && -r "$HOME/.config/claude/mcp-atlassian.env" ]]; then
    # Fallback for engineers still using the historical location.
    env_file="$HOME/.config/claude/mcp-atlassian.env"
fi
if [[ ! -r "${env_file}" ]]; then
    echo "atlassian-dc MCP is disabled: credentials file not readable: ${env_file}" >&2
    exit 2
fi
# shellcheck disable=SC1090
source "${env_file}"

if [[ -z "${MCP_ATLASSIAN_BIN:-}" ]]; then
    MCP_ATLASSIAN_BIN="$(command -v mcp-atlassian || true)"
fi
if [[ -z "${MCP_ATLASSIAN_BIN}" ]]; then
    echo "atlassian-dc MCP cannot find the mcp-atlassian executable; install with: pip install mcp-atlassian" >&2
    exit 2
fi
exec "${MCP_ATLASSIAN_BIN}" "$@"
