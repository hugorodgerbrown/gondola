# Testing

Every check runs through tox, locally and in CI, one CI job per env:

```bash
uv run tox                  # fmt, lint, types, checks, test, js, audit
uv run tox -e sast          # semgrep (downloads rule packs)
uv run pytest tests/groups  # a targeted run while iterating
```

## Which layer does a test belong in?

Work top-down and stop at the first layer that can hold the assertion. A
test in the wrong layer is a defect, whatever it asserts.

| Layer | Where | For |
| --- | --- | --- |
| **pytest** | `tests/` | Anything the Django test client can see: status codes, redirects, rendered HTML, htmx fragments, JSON, querysets, commands, headers. **A 401 needs no browser.** |
| **Vitest** | `tests/js/` | Anything a `static/js` file does that jsdom can observe. The default home for client-side behaviour. |

A browser suite (Playwright, `tests/e2e/`) arrives with the installed app
and its service worker, the first thing only a real browser can check.

## Rules

- Tests mirror the source tree: `apps/groups/views/days.py` is tested in
  `tests/groups/test_views.py`.
- Coverage floor is 90% (`pyproject.toml`); new code comes with tests.
- Factories live in `tests/factories.py`, one per model, always called as
  `Factory.create()` so mypy sees the model type.
- Every datetime has a timezone (ruff's `DTZ` rules enforce it).
- Query counts are asserted on list pages with
  `django_assert_max_num_queries`, so an N+1 fails a test, not production.
- Test functions are named for what they check and need no docstring
  (`D1` is off under `tests/`).
