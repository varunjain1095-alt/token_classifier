---
trigger: manual
---

# Implementation session

1. Restate the task in one sentence.
2. Read the architecture table of contents, the explicitly named sections, section 13 acceptance criteria and section 14 Windsurf instructions. Do not read unrelated sections.
3. Inspect the repository tree once. Use targeted search to identify the smallest relevant file set.
4. Before editing, list only the relevant files, intended change, validation command and any blocker.
5. Implement one bounded capability. Do not expand scope, redesign adjacent modules or refactor unrelated code.
6. Use real contracts and data paths. Never fabricate provider, database, pricing, token, classification or export results.
7. Run targeted validation once. Broaden validation only when the change crosses module boundaries or the targeted result exposes a concrete risk.
8. Stop when the task acceptance criteria pass.
9. Return a compact handoff: files changed; behaviour; validation and result; remaining limitation; architecture deviation.
