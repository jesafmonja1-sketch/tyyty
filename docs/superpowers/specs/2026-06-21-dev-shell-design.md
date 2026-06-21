# Dev Shell Design

## Overview

This design adds one local PowerShell helper for day-to-day use of the match analysis CLI.

The current project already works, but normal use still requires manually setting several
environment variables before each terminal session. The user does not want to focus on
email delivery right now. They want a fast way to enter a usable local analysis shell.

## Goal

Add one script that prepares a local PowerShell session for normal CLI analysis use.

The script should:

- set `PYTHONPATH` to the worktree `src` directory
- set `WCI_DATABASE_URL` to the real local SQLite database
- set the required email-related environment variables to harmless placeholder values
- print the next commands the user is expected to run

## Non-Goals

This phase will not:

- change the Python config model
- remove email fields from `Settings.from_env()`
- send email
- write secrets into the repository
- introduce cross-shell support beyond PowerShell

## Approaches Considered

### Option 1: Add a local PowerShell bootstrap script

Pros:

- smallest change
- matches the current Windows workflow
- avoids changing runtime behavior

Cons:

- PowerShell-specific

### Option 2: Relax Python settings so email variables become optional

Pros:

- cleaner long-term configuration model

Cons:

- changes runtime behavior
- requires broader regression coverage
- larger scope than needed for immediate use

### Option 3: Rely on a checked-in real `.env`

Pros:

- simple user experience

Cons:

- encourages local/private config to drift into the repo
- less explicit than a dedicated bootstrap entrypoint

## Recommendation

Use **Option 1**.

Add a PowerShell helper script and keep Python behavior unchanged. This is the fastest path
to normal use with the lowest regression risk.

## Proposed Files

Add:

- `scripts/dev-shell.ps1`

Optionally extend tests in:

- `tests/test_delivery_and_cli.py`

## Script Behavior

The script should:

1. resolve the repository root from the script location
2. set `PYTHONPATH` to `<repo>/src`
3. set `WCI_DATABASE_URL` to `sqlite:///C:/Users/Administrator/Documents/球赛/data/world-cup-intel.db`
4. set placeholder values for:
   - `WCI_EMAIL_SMTP_HOST`
   - `WCI_EMAIL_SMTP_PORT`
   - `WCI_EMAIL_USERNAME`
   - `WCI_EMAIL_PASSWORD`
   - `WCI_EMAIL_RECIPIENT`
5. print a short confirmation summary
6. print example commands for:
   - `python -m world_cup_intel.cli --help`
   - `python -X utf8 -m world_cup_intel.cli analyze-match 49`

The script should not invoke the CLI automatically. It should only prepare the shell.

## Error Handling

If the expected `src` path is missing, the script should fail clearly with a readable error.

No additional fallback search paths are needed for the first version.

## Testing Strategy

Keep testing lightweight.

Required coverage:

1. a test asserts that `scripts/dev-shell.ps1` exists
2. a test asserts that the script contains the required environment variable names
3. existing CLI tests remain green

This phase does not require integration-testing PowerShell invocation end to end.

## Success Criteria

This phase is successful when:

- the user can open PowerShell, run one script, and immediately use `analyze-match`
- no Python runtime behavior is changed
- no real email credentials are required for normal analysis usage

## Recommendation

Implement a single local `scripts/dev-shell.ps1` bootstrap script and keep all existing
application configuration behavior unchanged.
