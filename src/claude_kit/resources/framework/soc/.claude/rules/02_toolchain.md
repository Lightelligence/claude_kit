# Registered tool routing

For this Bazel project, `22_toolchain_bazel.md` owns build/integration tool
names and schemas. Use only servers enabled by the current project configuration;
generic Make-layout tools are not interchangeable with Bazel adapters.

- EDA execution uses registered MCP tools, never shell/Make fallbacks.
- Follow the **DV check menu** in `.claude/CLAUDE.md`. RTL lint does not check DV;
  compile-only validates the selected bench/test without simulation.
- `soc_sim` compiles before running. Do not run both `soc_comp` and `soc_sim`
  redundantly. Simulation, regression, coverage, synthesis and CDC require the
  engineer's selection; delivery or recovery does not grant execution approval.
- Process failures are tool errors. Verification requires current real logs;
  synthesis is structural evidence, not timing closure. Timing needs real STA
  evidence including WNS/TNS.
- Use enabled register/CRG generators for generated RTL. Never hand-write a
  generated clock/reset tree or invent an unavailable generator.
- OpenROAD uses its registered server. Keep project handoff files under
  `pd/openroad/`; external OpenROAD/ORFS source remains independent.
