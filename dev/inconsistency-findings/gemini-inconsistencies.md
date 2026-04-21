# gemini-inconsistencies

Repo-wide inconsistency report derived from a custom audit against the codebase,
`dev/consistency-checklists/claude-consistency.md`, and the other agents'
reports (`dev/inconsistency-findings/claude-inconsistencies.md` and
`dev/inconsistency-findings/codex-inconsistencies.md`).

Date: 2026-04-21

Confidence levels and Severities mirror the previous reports. This report explicitly evaluates both the **Code/Developer Perspective** (maintainability, safety, testability) and the **User Perspective** (UX, reliability, trust).

## 1. Confirmed findings (New or Expanded)

### 1. Script output styles bypass the repo-wide `rich` standard

*   **Status**: Confirmed mismatch
*   **Mechanism**: §3.4 — Success/warning/error coloring uses Rich markup.
*   **Code Perspective**: Scripts in `scripts/` (e.g., `build_ansible_collection.py`, `validate_regex.py`) duplicate output logic using bare `print()` and hardcoded unicode instead of leveraging the repo's established `rich.console.Console` tools.
*   **User Perspective**: Contributors and CI operators experience a jarring UI context switch. The polished CLI uses consistent colors and spinners, while dev scripts feel ad-hoc, untyped, and messy.
*   **Recommendation**: Standardize the scripts to use standard `rich` console rendering.

### 2. `sys.exit()` vs `click` teardown bypass

*   **Status**: Structural inconsistency
*   **Mechanism**: §1.1/§1.3 — `_dispatch()` error funnel
*   **Code Perspective**: `sccfm_cli/commands/base.py` calls `sys.exit(-1)` directly. This anti-pattern bypasses Click's `AppContext` teardown hooks and makes unit testing the CLI exit flows needlessly difficult.
*   **User Perspective**: Hard process exits can leave terminal states (like hidden cursors from spinners) corrupted or resources un-cleaned if interrupted. Users expect graceful teardowns.
*   **Recommendation**: Replace `sys.exit()` with `raise click.exceptions.Exit(...)` inside the base dispatcher.

### 3. Core services mixing `ValueError` vs `click.Abort` vs Catching

*   **Status**: Structural inconsistency
*   **Mechanism**: §10
*   **Code Perspective**: Domain services (`network_group_service.py`) raise `ValueError` for bad inputs. The CLI layer does not trap `ValueError` cleanly, blurring the lines between a bug (unhandled exception) and a user error (validation failure).
*   **User Perspective**: When a user provides invalid input that slips past `click` limits, they are hit with a raw Python stack trace instead of a styled `[red]Error: ...[/red]` message. This severely damages trust in the tool's stability.
*   **Recommendation**: Introduce a semantic `ValidationError` subclass inside `sccfm_core/errors.py` and trap it properly.

### 4. Over-reliance on `**kwargs` and `cast()` in `click` handlers

*   **Status**: Medium Severity Drift
*   **Mechanism**: §19.2 — `cast(...)` for kwargs unpacked from Click
*   **Code Perspective**: Parameters are extracted dynamically via `kwargs.get(...)` and typed with `cast()`. This defeats static analysis (`mypy`), creating a brittle codebase where unused or mistyped arguments fail only at runtime.
*   **User Perspective**: Users are more likely to experience weird runtime crashes during edge-case flag combinations because the compiler couldn't warn the developers that an argument was being cast incorrectly.
*   **Recommendation**: Move towards strict runtime validation bridging or strongly-typed CLI parameters.

## 2. Adjudication of other agents' findings

### A. Claude's Findings
(`dev/inconsistency-findings/claude-inconsistencies.md`)

- **H2 (`NameError` in FTD renderer)**: 
  - *Code Perspective:* Uncaught typo during refactoring that bypassed testing.
  - *User Perspective:* A total runtime crash whenever a user requests table output for FTD bulk CLI. High impact on reliability.
- **H1 (JSON via `console.print`)**: 
  - *Code Perspective:* Bleeds terminal formatting into data serialization streams.
  - *User Perspective:* Breaks user's `jq` pipelines and automation layers, rendering the `--format json` flag effectively useless and frustrating integration engineers.

### B. Codex's Findings
(`dev/inconsistency-findings/codex-inconsistencies.md`)

- **Ansible Error Handling Split (Item 13)**:
  - *Code Perspective:* 23 modules catch raw `Exception` instead of `ApiException`, circumventing the standardized API error models.
  - *User Perspective:* Playbook authors lose access to structured `error_code` and `error_details` fields, making it impossible to write `failed_when` conditions reliably in their Ansible pipelines.
- **Ansible Region Divergence (Items 1, 2, 28)**:
  - *Code Perspective:* Split definitions of truth for regions across CLI (`_REGIONS`) and Ansible (`ALLOWED_REGIONS`). Constant engineering drift.
  - *User Perspective:* Extreme frustration. A user configures `SCCFM_REGION=au` successfully in the CLI but gets rejected by Ansible, leading to confusion about which tool is broken or whether they misread the documentation.
