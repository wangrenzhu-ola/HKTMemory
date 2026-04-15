---
name: ga-project
description: Generate and manage the project knowledge base (HKTMemory). Use when the user asks to initialize, scan, or generate the project knowledge base.
---

# Gale Project Knowledge

This skill uses `gale knowledge store` to initialize or update the project's HKTMemory knowledge base.

## When To Use

- The user asks to generate the project knowledge base.
- The user asks to scan the project and save context.
- The user runs `/ga-project`.

## Workflow

1. Scan the current project to identify:
   - Project background and goals
   - Architectural constraints and tech stack
   - Team conventions, terminology, and historical decisions
2. Call `gale knowledge store` to persist these facts into the project's HKTMemory.
3. Confirm to the user that the project knowledge base has been generated.
