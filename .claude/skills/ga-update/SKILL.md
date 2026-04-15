---
name: ga-update
description: Check for Gale environment updates and apply them (runs gale update). Use when the user asks to update Gale, upgrade Gale, or fix the Gale installation.
---

# Gale Update

This skill executes `gale update` or `gale update --reinstall` in the terminal to synchronize the Gale AI Coding Environment with the latest stable version, or to reinstall the current checkout.

## When To Use

- The user asks to update Gale.
- The user reports that a command is missing or the installation is broken.
- The user asks to run `gale update`.

## Workflow

1. Run `gale update` in the terminal using the `RunCommand` or `Bash` tool.
2. If the user only wants to reinstall the current version without fetching from origin, run `gale update --reinstall`.
3. Report the result back to the user.
