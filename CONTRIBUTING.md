# Contributing

Thank you for your interest in contributing to **postgres-mcp-server**.

This project is stewarded by **Ashnik Technology Solutions Pvt Ltd** and community contributions are welcome.

Please read this guide before submitting changes.


## Project Governance

Project governance, stewardship, and maintainer responsibilities are described in:

GOVERNANCE.md

Ashnik Technology Solutions Pvt Ltd maintains the roadmap and release direction for the project.


## Types of Contributions

Contributions may include:

- bug fixes
- performance improvements
- documentation improvements
- tooling enhancements
- operational improvements
- security improvements

For large changes or architectural modifications, please open an **issue first** to discuss the proposal.


## Before Opening a Pull Request

Please ensure:

- changes are focused and easy to review
- production-safe defaults are preserved
- security practices are maintained
- documentation is updated when behavior changes

Avoid exposing:

- database credentials
- private infrastructure details
- sensitive configuration values


## Development Setup

Clone the repository and set up a Python virtual environment.


## Local setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Make your changes in a feature branch.

## Verification

Before submitting a pull request, verify that the codebase compiles
and contains no Python syntax errors.
```bash
python3 -m py_compile \
cli.py \
mcp_server/server.py \
mcp_server/db.py \
mcp_server/sql.py \
mcp_server/router.py \
mcp_server/tools/*.py


If your change affects **Claude Desktop integration**, verify that:

- launcher scripts still work
- env-file configuration flow remains intact
- MCP communication remains protocol-safe


## Contribution Guidelines

When contributing code:

- Keep **read-only behavior strict**
- Prefer **least-privilege database access**
- Keep **MCP stdio output clean and protocol-safe**
- Avoid unnecessary dependencies
- Maintain compatibility with existing MCP clients
- Follow the existing code structure


## Documentation

If your change affects setup, configuration, or usage:

- update `README.md`
- update relevant operational instructions
- add an entry in `CHANGELOG.md`


## Pull Request Process

Typical contribution workflow:

1. Fork the repository
2. Create a feature branch
3. Commit clear, descriptive changes
4. Verify the code compiles
5. Submit a pull request

Pull requests are reviewed by project maintainers before merging.


## Security Issues

If you discover a **security vulnerability**, please **do not open a public issue**.

Instead, report it privately to the maintainers so it can be addressed responsibly.


## License

By contributing to this repository, you agree that your contributions will be licensed under the **Apache License 2.0**, the same license that covers the project.

## Guidelines

- Keep read-only behavior strict
- Prefer least-privilege database access
- Keep MCP stdio output clean and protocol-safe
- Update `README.md` when user-facing setup changes
- Add an entry to `CHANGELOG.md` for notable changes
