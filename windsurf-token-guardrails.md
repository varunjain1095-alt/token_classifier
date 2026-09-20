# Windsurf Token-Use Guardrails

Version: 1.0  
Date: 18 September 2026  
Applies to: Review Classification Workbench

## Purpose

These guardrails minimize Windsurf token and credit use while preserving correctness. They control how Windsurf reads context, plans work, edits files, validates changes and reports completion.

They do not replace `classification-workbench-architecture.md`. The architecture defines the product. These rules define how Windsurf works on it.

## Recommended Windsurf setup

Use two workspace rules:

1. `.devin/rules/00-token-budget.md` with `trigger: always_on`. Keep this rule short because Windsurf includes its full content on every message.
2. `.devin/rules/implementation-session.md` with `trigger: manual`. Invoke it with `@implementation-session` only when beginning an implementation task.

Do not duplicate these rules in a root `AGENTS.md`, global rules or Memories. Duplicate always-on instructions consume context and can conflict.

Use `.devinignore` to exclude generated, dependency, build, coverage, cache, export and local-data directories from indexing. Create its final patterns only after the implementation stack and repository structure are selected; do not ignore source, migrations, tests or architecture files.

## Token budget principles

### 1. One bounded task per chat

Every implementation chat receives one phase, feature or defect with explicit acceptance criteria. Do not ask Windsurf to “build the application” in one conversation. Start a fresh chat when the working set changes materially or the current task is complete.

### 2. Give paths instead of pasting files

Reference the architecture file and exact relevant sections. Do not paste the architecture into chat. Reference existing code paths instead of copying their contents into prompts.

### 3. Read the smallest useful context

Windsurf must:

- inspect the repository tree once at the beginning of a task;
- locate relevant files with targeted search;
- read only the relevant sections/functions plus necessary adjacent context;
- reuse information already read in the same chat; and
- avoid rescanning the repository or rereading unchanged files.

Whole-repository reads, broad documentation ingestion, Codemaps, DeepWiki, Arena/multiple agents and web searches require an explicit task need. Do not use them by default.

### 4. Architecture retrieval is targeted

Before changing product behaviour, Windsurf reads the architecture table of contents and only the sections relevant to the task, plus the Windsurf instructions/acceptance criteria. It must cite the section IDs it is implementing. It must not restate the sections in its response.

If requirements conflict or a required decision is absent, Windsurf reports the exact conflict or missing decision and stops before implementation. It must not invent product behaviour.

### 5. No speculative expansion

Implement only the requested phase and its dependencies. Do not add future features, generalized frameworks, optional abstractions, alternative providers, unused configuration, speculative scalability, extra UI screens or “helpful” refactors.

Do not create documentation, tests, diagrams, sample data, seed data or migration scripts unless the task or acceptance criteria require them.

### 6. Prefer existing code and small diffs

Before creating a file, confirm that no existing module owns the behaviour. Modify the smallest coherent set of files. Preserve established patterns and dependencies. Do not rewrite a working file when a focused patch is sufficient.

Never replace real behaviour with mocks, placeholders, fabricated outputs or hard-coded success states. Do not claim an integration works without executing it against its real contract when the task requires that integration.

### 7. Plan briefly, then act

Before editing, Windsurf outputs at most:

- relevant files;
- intended change;
- validation command; and
- blocker, if any.

Do not produce long design essays when the architecture already decides the behaviour. Do not repeatedly ask for confirmation when the task is already authorized.

### 8. Tool-call discipline

- Batch independent searches when possible.
- Use targeted search before opening files.
- Do not run the same command again without a concrete reason.
- Do not install packages until the existing dependency files have been inspected.
- Do not use web search for stable language/framework facts already available locally.
- Do not launch development servers or watchers unless the task requires live verification.
- Stop background processes after verification.

### 9. Proportionate validation

Validate the smallest surface that proves the change:

1. targeted unit or contract test when meaningful;
2. affected module/type/lint check;
3. broader suite only when the change crosses module boundaries or a required gate demands it.

Do not generate redundant tests that merely mirror implementation. Do not repeatedly rerun a passing suite. Never report unexecuted checks as passed.

### 10. Compact handoff

The completion response contains only:

- files changed;
- behaviour implemented;
- validation actually executed and result;
- remaining limitation/blocker; and
- architecture deviation, if any.

Do not paste entire files, long diffs, logs or architecture summaries unless requested.

## Phase prompt template

Use this structure when assigning work:

```text
Implement: [one bounded capability]

Architecture source: classification-workbench-architecture.md
Read only: sections [IDs], section 13 acceptance criteria, and section 14 Windsurf instructions.

Scope:
- [required behaviour]
- [required behaviour]

Out of scope:
- [explicit exclusion]

Acceptance criteria:
- [observable result]
- [observable result]

Validation:
- [specific command or behaviour]

Use @implementation-session. Keep the diff minimal. Stop when these criteria pass.
```

## Session reset conditions

Start a new Windsurf chat when:

- moving to a new implementation phase;
- the task requires a mostly different file set;
- the conversation contains repeated summaries or stale failed approaches;
- a major architecture decision changes; or
- the current acceptance criteria have passed.

Carry forward only the accepted code state, current architecture version and new task prompt. Do not paste the previous chat transcript.

## Prohibited token-wasting behaviours

- Repeatedly summarizing the user request or architecture.
- Reading every file “for context.”
- Rebuilding a codebase map after one already exists in the chat.
- Generating multiple alternative implementations when one architecture is approved.
- Adding unsolicited features, refactors, comments or docs.
- Creating synthetic data or fake integrations to make the UI appear complete.
- Running broad tests after targeted validation has already proved an isolated change.
- Continuing after acceptance criteria pass.
- Using multiple agents or Arena mode unless explicitly requested.
- Saving durable Memories for information already present in version-controlled rules or architecture.

## User-controlled exceptions

The user may explicitly request broader exploration, multiple approaches, deeper testing, documentation, refactoring, web research or additional agents. The exception applies only to that task and does not permanently relax these guardrails.
