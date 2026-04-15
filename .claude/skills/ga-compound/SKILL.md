---
name: ga-compound
description: Execute the Compound Delivery Mode workflow. Use when the user wants to tackle a medium-sized task using brainstorm, plan, and work workflows, or when governed mode bridges to compound execution.
---

# Gale Compound Delivery Mode

Use the `gale` CLI to execute structured engineering workflows.

## When To Use

- The task size is medium or the risk is moderate.
- `gale mode decide` outputted `selected_mode: compound`.
- Bridging from a governed OpenSpec change into implementation.

## Commands

- `gale compound brainstorm <task>`: Prepare HKTMemory context and execute `/ce:brainstorm`.
- `gale compound plan [--bridge-path <path>]`: Prepare HKTMemory context and execute `/ce:plan`.
- `gale compound work <plan-path>`: Reuse the prepared context and execute `/ce:work`.
- `gale compound review [--plan-path <path>]`: Execute `/ce:review`.
- `gale compound compound [--mode <lightweight|full>]`: Execute `/ce:compound` and sync the solution into HKTMemory.

## Recall Rules

- Follow Gale's mode-specific context rules instead of forcing ad-hoc recall before every step.
- `brainstorm` and `plan` prepare knowledge context by default.
- `work` and `review` normally reuse the current session context; only add extra recall when the current context is insufficient.

## Mandatory Closeout

- Every completed `brainstorm` / `plan` / `work` / `review` stage must end with `gale compound compound` before the stage is considered closed.
- Prefer `--mode lightweight` for intermediate phase summaries and `--mode full` for the final end-to-end task summary.

## Example Flow

1. Brainstorm: `gale compound brainstorm "<task>"` -> `gale compound compound --mode lightweight --context "brainstorm stage summary"`
2. Planning: `gale compound plan [--bridge-path <path>]` -> `gale compound compound --mode lightweight --context "plan stage summary"`
3. Execution: `gale compound work <plan-path>` -> `gale compound compound --mode lightweight --context "work stage summary"`
4. Review: `gale compound review [--plan-path <path>]` -> `gale compound compound --mode full --context "review stage summary"`
