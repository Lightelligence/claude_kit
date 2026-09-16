# DV change checks

Read only the affected component's guidance. Match project/UVM version and local
architecture; do not convert a small test change into an environment rewrite.

- **Scenario:** Tie stimulus to a requirement and observable expected result.
  Include legal boundaries, reset/backpressure or error injection when relevant.
  Check randomization failures and reachability; a test that sends no transactions
  must not report the intended scenario as exercised.
- **Driver/sequence:** Define acceptance, completion and response ownership.
  Handle reset interruption and outstanding items consistently; respect the
  interface timing rather than guessing delays.
- **Monitor:** Sample at the agreed event/skew, count accepted transfers once and
  preserve complete transaction data. If a consumer retains an object, provide
  stable ownership or a snapshot; immediate consumption does not require cloning.
- **Scoreboard/model:** Define ordering/ID matching, masks, latency, error handling
  and reset/flush of pending predictions. Detect missing/extra responses before
  test completion. Keep the oracle independent of the DUT result under test.
- **Assertions/coverage:** Match sampling/enables to real transactions and relevant
  requirements. Track activation/coverage as intended until an actual run supports
  it. Do not weaken checks or exclusions simply to obtain a pass.
- **Integration:** Reuse factory/configuration/TLM conventions and the existing
  build/test selector. Inspect compile-order dependencies when adding files.
  Avoid silently changing unrelated tests or hard-coding one project's aliases.
- **End condition:** Distinguish stimulus completion from checker drain; provide
  bounded timeout and useful diagnostics. Preserve the original failure on retry.

Static inspection is not compilation. Present applicable compile checks to the
engineer; no simulation, regression or broader run follows automatically.
