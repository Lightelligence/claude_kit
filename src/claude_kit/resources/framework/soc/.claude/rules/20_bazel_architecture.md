---
paths:
  - "**/BUILD"
  - "**/BUILD.bazel"
  - "**/*.bzl"
  - "WORKSPACE*"
---

# Bazel integration

Read the consumer's profile and repository-layout reference for actual source
roots, SoC hierarchy and vendor repositories. Do not infer a test label from a
module name. Inspect existing BUILD and dependency rules before changing them.

Use registered build/integration MCP tools and the project's selected checks and
execution route. Dependency-query output is not a generated compile inventory;
use the configured testbench's generated inputs for LSP indexing. Preserve the
distinction between generating inputs, compiling, simulating and signoff.

Keep integration edits in the integrator's scope, RTL edits in the designer's
scope and test changes in the verification owner's scope. Preserve vendor IP
boundaries and generated-file ownership. Follow the selected stage gates.
