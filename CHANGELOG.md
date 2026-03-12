# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows semantic-style release notes where practical.

## [Unreleased]

### Added
- Structured audit logging with a new `audit_logs` MCP tool
- Claude Desktop launcher scripts for separate local and remote database targets
- Private `.env.claude.*` workflow to avoid storing credentials in Claude config
- Shared SQL helpers for validation, read-only execution, and explain-plan access

### Changed
- Switched the Claude launcher flow to use the repo virtualenv
- Updated README with secure Claude Desktop setup, local/remote configuration, and clearer quick-start guidance
- Improved database pool reuse and query execution flow across the server

### Security
- Enforced read-only SQL execution with PostgreSQL read-only transactions
- Removed the need to place database credentials directly in `claude_desktop_config.json`
