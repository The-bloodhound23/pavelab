# AGENTS.md: rules for AI coding agents (Claude, ChatGPT/Codex)

Read `docs/PROJECT_STATUS.md` and `docs/ARCHITECTURE.md` before starting any task.

## Workflow
- Work only on an Issue labelled for you (`claude` or `chatgpt`). Claim it in `docs/PROJECT_STATUS.md` under "In progress".
- One branch per Issue (`feat/…`, `fix/…`, `docs/…`), opened as a pull request against `main` that says `Closes #N`.
- Never push to `main`, merge, tag a release, publish to PyPI, deploy, or post publicly. Bolu (@The-bloodhound23) approves all of these.
- Review the other agent's pull requests when asked. Comment on bugs, missing tests and rule breaks; don't push to their branch.
- Update `docs/PROJECT_STATUS.md` (Done, In progress, Decision log) and `CHANGELOG.md` in the same PR as the change.

## Engineering rules
- **Numbers come from tested code.** PCI, forecasts and LCCA are computed in `pavelab`, never by an LLM, and never duplicated in another language without a cross-check test.
- **No fabricated PCI.** A standards-based PCI needs sample units, distress type, severity, quantity and an approved curve set. Otherwise the output is a "preliminary condition estimate" and is labelled that way.
- **Never commit ASTM D6433 deduct or CDV curves** or other copyrighted standard text. `data/example_curves.json` is illustrative and must stay labelled so.
- **Every forecasting change reports the carry-forward baseline** (`PersistenceForecaster`), evaluated with whole road sections held out.
- **Backward compatible by default.** New options default to current behaviour, and existing tests must pass unchanged.
- **Data:** only sources whose licence allows commercial use (see `tools/harvester`). No page scraping and no downloading of YouTube video. No private municipal data and no unpublished paper results in the repo.

## Code standards
- Python 3.9+, dependencies kept to numpy and scipy in the library. Optional extras go in `[project.optional-dependencies]`.
- Type hints and docstrings on public functions. A docstring that implements a published method cites it, paraphrased, not quoted.
- Tests in `tests/` with pytest. Every new public function gets tests, including at least one hand-checked numeric case.
- Before opening a PR, run `pytest -q` and `python examples/quickstart.py`. CI runs both on Python 3.9, 3.11 and 3.12.
- End commits with your agent attribution line.
