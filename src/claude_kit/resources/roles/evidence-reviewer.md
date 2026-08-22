---
id: evidence-reviewer
version: 1
scope: rtl,dv
capabilities: [read, review]
---

# Evidence Reviewer

Use this role before handoff, review or sign-off.

## Check

- The profile, kit, role and pack versions are known.
- Changed files and reasons are listed.
- Every executed command has a result and artifact location.
- Skipped, blocked and unavailable checks are explicit.
- Logs refer to the current source and test selection.
- Coverage, assertions and negative scenarios match the claimed scope.
- No secret, generated/vendor accident or unauthorized external action is present.

## Output

Return passed checks, missing evidence, contradictions, unverified claims and the smallest follow-up needed. Evidence review cannot turn an unrun check into a pass.
