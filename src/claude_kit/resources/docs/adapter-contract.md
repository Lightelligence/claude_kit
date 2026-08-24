# Project Adapter Contract

The adapter is optional. Use it when a project has target aliases, test selectors, VIP mappings or artifact collection that should not be embedded in a generic profile.

Keep these concerns in the project:

- real RTL/DV paths and target names;
- simulator and build wrapper invocation;
- VIP class, instance and interface names;
- project-specific artifact locations;
- project-specific environment checks.

If results live outside the checkout, declare the project's regression root
and compile/simulation naming rules under `[artifacts.regression]` in the
project profile. The kit provides bounded discovery and log-reading tools;
the adapter or project MCP server remains responsible for mapping a real
check run to its target, test, run id, and returned artifact paths. Do not put
one checkout's absolute path or test alias into the generic kit.

Keep these concerns in claude_kit:

- generic roles and skills;
- protocol/VIP reasoning and checklists;
- profile, manifest, artifact and evidence schemas;
- path and command safety rules;
- context resolution and evidence review.

An adapter should expose small deterministic functions such as resolve_target, resolve_test, resolve_vip and collect_artifacts. It should not import project RTL/DV modules into the kit or require an ETX runner.

The conventional signatures are:

- `resolve_target(name)`;
- `resolve_test(selector)`;
- `resolve_vip(protocol)`;
- `collect_artifacts(run_id)`.

`claude-kit adapter check` imports the adapter and checks that required functions exist and accept at least one argument. It does not call those functions or execute project tools; behavior still needs an allowlisted command and evidence.
