====================================
Cisco SCCFM Collection Release Notes
====================================

.. contents:: Topics

v0.43.0
========

Minor Changes
-------------

- Added direct Amazon Bedrock support to the SCCFM agent harness with isolated command execution, schema-grounded evaluation, and stronger credential-safety checks.

v0.42.1
========

Bugfixes
--------

- Bumped the SCCFM SDK to 1.22.1573 to support unknown licensing statuses and aligned multi-device FTD deployments with the current SDK API.

v0.42.0
========

Minor Changes
-------------

- Added Claude support to the SCCFM agent harness with provider credential isolation, runtime-only retries, source-aware comparison fingerprints, more reliable deterministic command evidence, and clearer diagnostics.

Bugfixes
--------

- Corrected plugin runtime ownership handling so incomplete Homebrew companions cannot be silently overwritten or removed through the wrong uninstall flow.

v0.41.1
========

Minor Changes
-------------

- Added a local and CI-compatible SCCFM agent harness with deterministic command doubles, reliability reporting, installed-plugin freshness checks, and safer guarded Ansible check-mode confirmation.

v0.41.0
========

Minor Changes
-------------

- Improved the SCCFM agent plugin with faster version-aligned setup, optional Homebrew CLI installation, a managed Ansible companion for Homebrew installs, safer exact-command approvals, and digest-bound runtime cleanup.

v0.40.2
========

Bugfixes
--------

- Corrected Homebrew release automation to resolve Core dependencies through the Formula API, support dry-run validation, and enable protected automatic merging of successful tap updates.

v0.40.1
========

Minor Changes
-------------

- Added release automation that updates the SCCFM CLI Homebrew formula from the verified PyPI source distribution and opens a pull request in the CiscoDevNet tap.

v0.40.0
========

Minor Changes
-------------

- Added an installable agent plugin for Claude Code and Codex with guided SCCFM runtime setup, synchronized CLI and Ansible skills, and exact-command approval guardrails for mutating operations.

v0.39.5
========

Minor Changes
-------------

- Added public-release smoke progress logging for registry resolution, artifact installation, plugin discovery, offline probes, and profile handoff validation.

v0.39.4
========

Bugfixes
--------

- Fixed manual release promotion so verified draft assets are handed off to read-only PyPI and Galaxy publication jobs.

v0.39.3
========

Bugfixes
--------

- Corrected development setup and Ansible example guidance so collection installation, Vault handling, profile lookup safety, and command failures follow the supported workflows.

v0.39.2
========

Bugfixes
--------

- Added the documented ``sccfm-cli-interactive`` command to the paired Python package while keeping repository maintenance tasks out of public artifacts.

v0.39.1
=======

Release Summary
---------------

Initial development release of the cisco.sccfm collection, with dynamic inventory and modules for automating Cisco Security Cloud Control Firewall Manager. This release unifies CLI and Ansible authentication around canonical SCCFM profiles and prepares the paired Python and Galaxy artifacts for secure publication.
