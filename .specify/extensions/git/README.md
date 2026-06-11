# Git Branching Workflow Extension

A self-contained [Spec Kit](https://github.com/github/spec-kit) extension that wires Git into the spec-driven workflow: repository initialization, numbered feature branches, branch validation, remote detection, and opt-in auto-commits around every core command.

- [Features](#features)
- [Installation](#installation)
- [Commands](#commands)
- [Lifecycle hooks](#lifecycle-hooks)
- [Configuration](#configuration)
- [Graceful degradation](#graceful-degradation)
- [Bundled scripts](#bundled-scripts)
- [Requirements](#requirements)

## Features

- **Repository initialization** — creates the repo and an initial commit with a configurable message before constitution setup.
- **Feature branch creation** — branches are numbered automatically, either sequentially (`001-feature-name`) or by timestamp (`20260319-143022-feature-name`).
- **Branch validation** — verifies the current branch follows the feature-branch naming convention before work proceeds.
- **Remote detection** — resolves the Git remote URL so GitHub integrations (such as issue creation) know where to point.
- **Auto-commit** — optionally commits outstanding changes before and/or after each core Spec Kit command, with a customizable message per hook.

## Installation

The extension ships bundled with Spec Kit — no network access required:

```bash
specify extension add git
```

To turn it off without uninstalling (spec creation continues, just without branching):

```bash
specify extension disable git
specify extension enable git    # re-enable later
```

## Commands

| Command | Description |
|---------|-------------|
| `speckit.git.initialize` | Initialize a Git repository with a configurable initial commit message |
| `speckit.git.feature` | Create a feature branch with sequential or timestamp numbering |
| `speckit.git.validate` | Validate that the current branch follows feature-branch naming conventions |
| `speckit.git.remote` | Detect the Git remote URL for GitHub integration |
| `speckit.git.commit` | Commit changes, driven by the per-hook `auto_commit` configuration |

## Lifecycle hooks

Two hooks are **required** and run automatically:

| Event | Command | Purpose |
|-------|---------|---------|
| `before_constitution` | `speckit.git.initialize` | Ensure a Git repository exists before constitution setup |
| `before_specify` | `speckit.git.feature` | Create the feature branch before specification begins |

Every other core command is wrapped by an **optional** `speckit.git.commit` hook on both sides — `before_*` commits outstanding changes so the command starts from a clean tree, `after_*` snapshots its output. Covered commands: `clarify`, `plan`, `tasks`, `implement`, `checklist`, `analyze`, and `taskstoissues`, plus `after_constitution` and `after_specify`. All optional hooks are disabled by default and prompt before committing when enabled interactively.

## Configuration

Installed to `.specify/extensions/git/git-config.yml` (from `config-template.yml`):

```yaml
# Branch numbering strategy: "sequential" (001, 002, ...) or "timestamp" (YYYYMMDD-HHMMSS)
branch_numbering: sequential

# Commit message used during repository initialization
init_commit_message: "[Spec Kit] Initial commit"

# Auto-commit before/after core commands.
# "default" applies to every hook; override per-hook below it.
auto_commit:
  default: false
  after_specify:
    enabled: true
    message: "[Spec Kit] Add specification"
  before_implement:
    enabled: true
    message: "[Spec Kit] Save progress before implementation"
```

Each `before_*`/`after_*` key accepts `enabled` (boolean) and `message` (string). Hooks not listed inherit `default`.

## Graceful degradation

Git is an optional dependency. When it is not installed, or the working directory is not a Git repository:

- Spec directories are still created under `specs/`
- Branch creation and validation are skipped with a warning
- Remote detection returns empty results

Nothing in the core Spec Kit workflow hard-fails on a missing Git setup.

## Bundled scripts

Cross-platform implementations live under `scripts/`:

| Script | Role |
|--------|------|
| `scripts/bash/create-new-feature.sh` | Feature branch creation (Bash) |
| `scripts/bash/git-common.sh` | Shared Git utilities (Bash) |
| `scripts/bash/initialize-repo.sh` | Repository initialization (Bash) |
| `scripts/bash/auto-commit.sh` | Auto-commit hook runner (Bash) |
| `scripts/powershell/create-new-feature.ps1` | Feature branch creation (PowerShell) |
| `scripts/powershell/git-common.ps1` | Shared Git utilities (PowerShell) |
| `scripts/powershell/initialize-repo.ps1` | Repository initialization (PowerShell) |
| `scripts/powershell/auto-commit.ps1` | Auto-commit hook runner (PowerShell) |

## Requirements

- Spec Kit `>= 0.2.0`
- `git` on `PATH` (optional — see [Graceful degradation](#graceful-degradation))

Maintained by `spec-kit-core` · MIT licensed · [github/spec-kit](https://github.com/github/spec-kit)
