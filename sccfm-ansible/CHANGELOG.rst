====================================
Cisco SCCFM Collection Release Notes
====================================

.. contents:: Topics

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
