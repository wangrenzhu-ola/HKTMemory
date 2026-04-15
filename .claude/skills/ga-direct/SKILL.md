---
name: ga-direct
description: Execute the Direct/Chat Delivery Mode workflow. Use for small bug fixes, typo corrections, or minor edits that do not require structured planning or formal governance.
---

# Gale Direct Delivery Mode

Execute low-risk tasks directly while keeping recall and knowledge write-back aligned with Gale's design.

## When To Use

- The task size is small and the risk is low.
- `gale mode decide` outputted `selected_mode: direct`.
- Quick bug fixes or minor code edits.

## Workflow

### Step 1: Decide Whether Recall Is Needed

- If the task depends on project terminology, prior decisions, architecture constraints, or earlier solutions, run `gale knowledge query <query>` before implementation and show the relevant output.
- If the task is isolated and current context is already sufficient, you may proceed without an extra recall step.
- Do not force a knowledge query on every direct task unless the design context actually requires it.

### Step 2: Execute

### Step 3: Write Context (Conditional)

**This step is required if the change introduces a new pattern, stabilizes a decision, or creates a new file.**

### Step 3: Knowledge Closeout (Conditional)

**This step is required if the change introduces a new pattern, stabilizes a decision, or creates reusable knowledge.**

- Prefer `gale compound compound --mode lightweight --context "<change summary>"` as the default knowledge closeout path.
- Use `gale knowledge store` only when you need to补录 a small fact that does not warrant a `ce:compound` solution artifact.
- Show the resulting output when a knowledge write-back step is performed.

- Show the full command and full output for every executed step without omitting details

- Make the recall decision explicit when it matters to the task.
- If the request is only a documentation update or a simple correction, Step 3 may be skipped, but the response must state why it was skipped
2. Any code change must have the Step 1 query output visible first as execution context
3. Any change involving a new pattern or new decision must also show the `gale knowledge store` output
1. Any external agent running `/ga-direct <simple task>` must decide recall based on task context rather than blindly querying every time
2. Any task that depends on project memory must show the relevant `gale knowledge query` output before implementation work
3. Any change involving a new pattern or new decision should prefer `gale compound compound` as the knowledge closeout step
4. `gale knowledge store` remains available for narrow补录, not as the default closeout path
