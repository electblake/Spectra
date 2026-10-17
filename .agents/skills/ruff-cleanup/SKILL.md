---
name: ruff-cleanup
description: Use automatically after creating, editing, or refactoring Python files in a project with Ruff available. Apply safe Ruff lint fixes to task-scoped changed files before the final response, even when cleanup is not explicitly requested.
---

# Ruff Cleanup

Finish Python code changes with a Ruff cleanup pass before the final response.

- Use the current project's existing Ruff installation, runner, and configuration.
- Run `ruff check --fix -- <files>` on changed Python files within the task's scope, including new files.
- Skip when no Python files changed or Ruff is not provided.
- Apply safe fixes only. Do not change lint configuration, add suppressions, or expand into formatting or manual refactoring.
- Review the resulting diff and run relevant tests if fixes affect behavior.
- Report unresolved diagnostics or execution failures without hiding them.
