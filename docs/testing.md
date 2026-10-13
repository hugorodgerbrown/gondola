# Testing

Every check runs through tox, locally and in CI, one CI job per env:

```bash
uv run tox                  # fmt, lint, types, checks, test, js, audit
uv run tox -e sast          # semgrep (downloads rule packs)
uv run tox -e e2e           # Playwright journeys (needs a Chromium)
uv run pytest tests/groups  # a targeted run while iterating
```

## Which layer does a test belong in?

Work top-down and stop at the first layer that can hold the assertion. A
test in the wrong layer is a defect, whatever it asserts.

| Layer | Where | For |
| --- | --- | --- |
| **pytest** | `tests/` | Anything the Django test client can see: status codes, redirects, rendered HTML, htmx fragments, JSON, querysets, commands, headers. **A 401 needs no browser.** |
| **Vitest** | `tests/js/` | Anything a `static/js` file does that jsdom can observe. The default home for client-side behaviour. |
| **Playwright** | `tests/e2e/` | Only what needs a real browser: the service worker, Cache Storage, going offline and back. |

## Journeys

The browser suite is capped (`tests/test_e2e_budget.py`: 12 tests, 40
lines each). Each journey is named in its module docstring.

| Journey | Test |
| --- | --- |
| Offline fallback: an unvisited page shows "No signal"; a visited one opens from cache | `test_offline_page.py` |
| Offline write: a day saved with no signal waits on the phone, then sends | `test_offline_write.py` |

Locally, point Playwright at a Chromium you have with
`PLAYWRIGHT_CHROMIUM_EXECUTABLE`; CI installs its own.

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
