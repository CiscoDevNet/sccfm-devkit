# sccfm-api-cli

## Dev environment tips
- Use `poetry` for dependency management.
- Use `black` for syntax formatting.
- Use `isort` for import sorting.
- Use `mypy` for static type checking.
- Use `pytest` for testing.
- Use `coverage` for test coverage.
- Use `pre-commit` for pre-commit hooks.
- Use `click` for CLI configuration
- Use `rich` for command-line output
- Use `questionary` for user prompts
- Add virtualenv scripts.
- The code should be structured in a way that it can be easily extended. Use the command pattern for each command.
- Each external library we use - for example, the scc firewall SDK and the pyvmomi libraries - should be put into a separate services directory.
- Humans will be extending this code; do not generate AI slop. No long methods!
- Use Python type hints strictly. Do not write code without typing.

## Commit and PR instructions
- Do not commit. I will do it.
