---
name: ga-govern
description: Execute the Governed Delivery Mode workflow. Use when the user wants to start or continue a long-running, high-risk, or complex task using OpenSpec governance artifacts (proposal, design, specs).
---

# Gale Governed Delivery Mode

Use the `gale` CLI to execute tasks with rigorous project governance.

## When To Use

- The task size is large or the risk is high.
- `gale mode decide` outputted `selected_mode: governed`.
- The user explicitly requests governed mode, proposal, design, or specs.

## Governed Mode Defaults

Human-in-the-loop is mandatory by default:
- Treat `proposal`, `design`, `specs`, and final closeout as approval gates.
- At the end of each gate, stop and ask the user whether to continue before proceeding.
- Use the platform's blocking question tool (e.g., `AskUserQuestion`) if available.
- After user approval, record it with `gale govern approve <artifact>`.
- After each completed `proposal` / `design` / `specs` stage, run `gale compound compound --mode lightweight --context "<artifact> stage summary"` to summarize stable knowledge into HKTMemory before moving on.
- After each downstream `brainstorm` / `plan` / `work` / `review` stage, also run `gale compound compound` before considering that stage closed.
- Do not advance between gates without explicit user approval recorded in the CLI state.

## Example Flow

1. Start: `gale govern start <change-id>`
2. Proposal: `gale govern instructions proposal` -> create artifact -> `gale govern review proposal` -> wait for user -> `gale govern approve proposal` -> `gale compound compound --mode lightweight --context "proposal stage summary"`
3. Design: `gale govern instructions design` -> create artifact -> `gale govern review design` -> wait for user -> `gale govern approve design` -> `gale compound compound --mode lightweight --context "design stage summary"`
4. Specs: `gale govern instructions specs` -> create artifact -> `gale govern review specs` -> wait for user -> `gale govern approve specs` -> `gale compound compound --mode lightweight --context "specs stage summary"`
5. Bridge: `gale bridge generate` -> hand off to `/ga-compound` (brainstorm/plan/work/review, each stage ending with `gale compound compound`)
6. Closeout: Execute implementation, test, run a final `gale compound compound` if needed, then `gale govern approve final` -> `gale govern archive`
