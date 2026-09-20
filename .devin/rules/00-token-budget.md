# Token Budget Rule

Always follow the token guardrails in `windsurf-token-guardrails.md`. Keep responses concise and focused on the specific task. Do not generate unnecessary code, documentation, or explanations.

## Key Principles:
- One bounded task per chat
- Read only relevant files/sections
- Prefer small diffs over large rewrites
- No speculative expansion beyond the task
- Proportionate validation (test only what's needed)
- Compact handoff (files changed, validation run, limitations)