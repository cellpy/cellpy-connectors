# Test registry

Living index of notable tests for the optional **essential tests** paradigm
(see [essential-tests.md](./essential-tests.md)). Seeded once by issue-flow;
**never overwritten** on `issue-flow update` — agents and humans grow the table.

When `[issueflow].essential_tests` is true, `/iflow-close` / `/iflow-build`
(per `essential_review`) should add or update rows for tests **touched by the
current issue**. `/iflow-doctor` may audit the whole suite against this table.

| Test (node id or path::name) | Essential? | Always? | Code under test | Issue | Notes / demote? |
| --- | --- | --- | --- | --- | --- |
| tests/test_cli.py::test_package_imports | no | | cellpy_connectors | #4 | First suite; no essential marker configured |
| tests/test_cli.py::test_entry_point_is_declared | no | | pyproject entry point | #4 | |
| tests/test_cli.py::test_ping_via_app | no | | cellpy_connectors.cli | #4 | |
| tests/test_cli.py::test_cellpy_help_lists_connectors_without_import | no | | cellpy mount | #4 | skips without CellpyCLIGroup |
| tests/test_cli.py::test_cellpy_connectors_ping | no | | cellpy mount | #4 | skips without CellpyCLIGroup |
| tests/test_cli.py::test_import_cellpy_does_not_import_connectors | no | | cellpy import | #4 | skips without cellpy |
| tests/test_cli.py::test_entry_point_loads_typer_app | no | | cellpy_connectors.cli | #4 | |

**Columns**

- **Essential?** — currently marked with the configured pytest marker.
- **Always?** — should stay essential even after the originating issue closes.
- **Code under test** — modules/symbols (graphify can help).
- **Issue** — GitHub number that introduced or last reviewed the test.
- **Notes / demote?** — why essential, or candidate for demotion.
