#!/usr/bin/env bash
# Launch the optional xverif MCP server without embedding site paths or
# credentials in the repository configuration.
set -Eeuo pipefail

xverif_home="${XVERIF_HOME:-}"
if [[ -z "${xverif_home}" || ! -d "${xverif_home}" ]]; then
    echo "xverif MCP is disabled: set XVERIF_HOME to a licensed xverif checkout" >&2
    exit 2
fi

python_bin="${XVERIF_PYTHON:-${PYTHON:-python3}}"
if ! command -v "${python_bin}" >/dev/null 2>&1; then
    echo "xverif MCP cannot find Python executable: ${python_bin}" >&2
    exit 2
fi

export XVERIF_HOME="${xverif_home}"
# Use the selected MCP interpreter for xcov unless explicitly overridden.
export XVERIF_XCOV_PYTHON="${XVERIF_XCOV_PYTHON:-${python_bin}}"
export PYTHONPATH="${XVERIF_HOME}/xverif_mcp/src:${XVERIF_HOME}${PYTHONPATH:+:${PYTHONPATH}}"
exec "${python_bin}" -m xverif_mcp.server "$@"
