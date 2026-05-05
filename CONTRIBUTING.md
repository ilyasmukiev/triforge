# Contributing to triforge

Thanks for your interest! `triforge` is alpha and the API is still moving — your feedback and PRs are welcome.

## Quick start

```bash
git clone https://github.com/ilyasmukiev/triforge.git
cd triforge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install  # if/when configured
```

## Tests

```bash
pytest                    # fast unit tests
pytest -m slow            # integration tests (hit real LLMs)
pytest --cov=triforge     # with coverage
```

## Style

- Type-checked with `mypy --strict`.
- Linted with `ruff`.
- 100-character lines, Python ≥ 3.10.

## Pull requests

1. Open an issue first for non-trivial changes.
2. Add tests; aim for ≥ 80 % coverage of new code.
3. Update `CHANGELOG.md` under `[Unreleased]`.
4. Make sure `pytest`, `mypy`, `ruff check` are all green.

## License

By contributing, you agree that your contributions will be licensed under [Apache-2.0](./LICENSE).
