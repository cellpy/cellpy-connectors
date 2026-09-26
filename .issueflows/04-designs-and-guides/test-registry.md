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
| tests/test_cli.py::test_configure_unknown_name | no | | cellpy_connectors.cli | #1 | lists shipped connectors (batbase) |
| tests/test_cli.py::test_configure_stores_without_echoing_the_secret | no | | cellpy_connectors.cli | #3 | fake keyring |
| tests/test_credentials.py::test_explicit_beats_environment | no | | cellpy_connectors.credentials | #3 | |
| tests/test_credentials.py::test_explicit_secretstr_is_kept | no | | cellpy_connectors.credentials | #3 | repr hides the value |
| tests/test_credentials.py::test_empty_explicit_falls_through_to_env | no | | cellpy_connectors.credentials | #3 | |
| tests/test_credentials.py::test_environment_beats_keyring | no | | cellpy_connectors.credentials | #3 | |
| tests/test_credentials.py::test_keyring_when_env_unset | no | | cellpy_connectors.credentials | #3 | |
| tests/test_credentials.py::test_missing_keyring_is_not_configured | no | | cellpy_connectors.credentials | #3 | NoKeyringError |
| tests/test_credentials.py::test_store_secret_writes_keyring | no | | cellpy_connectors.credentials | #3 | |
| tests/test_credentials.py::test_store_secret_without_backend | no | | cellpy_connectors.credentials | #3 | |
| tests/test_client.py::test_session_retries_idempotent_methods_only | no | | cellpy_connectors.client | #3 | no live HTTP |
| tests/test_client.py::test_401_is_auth_error | no | | cellpy_connectors.client | #3 | |
| tests/test_client.py::test_500_is_connector_error | no | | cellpy_connectors.client | #3 | |
| tests/test_client.py::test_network_error_is_connector_error | no | | cellpy_connectors.client | #3 | |
| tests/test_client.py::test_check_connection_returns_ok | no | | cellpy_connectors.client | #3 | |
| tests/test_batbase.py::test_batbase_spec_is_registered | no | | cellpy_connectors.batbase / registry | #1 | |
| tests/test_batbase.py::test_resolve_base_url_precedence | no | | cellpy_connectors.batbase.resolve_base_url | #1 | |
| tests/test_batbase.py::test_api_path_normalisation | no | | cellpy_connectors.batbase.api_path | #1 | parametrised |
| tests/test_batbase.py::test_fetch_token_uses_basic_auth_and_client_credentials_grant | no | | BatBaseClient.fetch_token | #1 | wire shape of POST o/token/ |
| tests/test_batbase.py::test_token_is_cached_until_close_to_expiry | no | | BatBaseClient.token | #1 | injected clock |
| tests/test_batbase.py::test_requests_carry_bearer_and_reuse_token | no | | BatBaseClient.request | #1 | |
| tests/test_batbase.py::test_401_triggers_one_reauth_then_raises | no | | BatBaseClient._request | #1 | no infinite loop |
| tests/test_batbase.py::test_rejected_client_credentials_raise_auth_error | no | | BatBaseClient.fetch_token | #1 | |
| tests/test_batbase.py::test_missing_credentials_error_names_env_vars_and_configure | no | | BatBaseClient.credentials | #1 | no network without creds |
| tests/test_batbase.py::test_anonymous_mode_sends_no_authorization | no | | BatBaseClient | #1 | |
| tests/test_batbase.py::test_anonymous_403_gives_hint | no | | BatBaseClient | #1 | |
| tests/test_batbase.py::test_secret_never_appears_in_error_text | no | | BatBaseClient | #1 | secret hygiene |
| tests/test_batbase.py::test_get_all_follows_drf_pagination | no | | BatBaseClient.get_all | #1 | |
| tests/test_batbase.py::test_get_all_handles_unpaginated_list_and_single_object | no | | BatBaseClient.iter_rows | #1 | |
| tests/test_batbase.py::test_non_json_response_is_connector_error | no | | BatBaseClient.get | #1 | |
| tests/test_batbase.py::test_http_500_is_connector_error_not_auth_error | no | | BatBaseClient | #1 | |
| tests/test_batbase.py::test_cli_get_prints_json | no | | cli.batbase_get | #1 | stub client |
| tests/test_batbase.py::test_cli_get_all_and_anonymous | no | | cli.batbase_get | #1 | |
| tests/test_batbase.py::test_cli_get_rejects_malformed_param | no | | cli._parse_params | #1 | |
| tests/test_batbase.py::test_cli_check_reports_connection | no | | cli.batbase_check | #1 | |
| tests/test_batbase.py::test_cli_auth_error_exits_1_without_traceback | no | | cli.batbase_check | #1 | |
| tests/test_batbase.py::test_cli_configure_batbase_uses_registered_fields | no | | cli.configure + batbase spec | #1 | fake keyring |
| tests/test_batbase.py::test_basic_auth_header_shape_matches_batbase_scripts | no | | requests Basic auth | #1 | parity with BatBase scripts |

**Columns**

- **Essential?** — currently marked with the configured pytest marker.
- **Always?** — should stay essential even after the originating issue closes.
- **Code under test** — modules/symbols (graphify can help).
- **Issue** — GitHub number that introduced or last reviewed the test.
- **Notes / demote?** — why essential, or candidate for demotion.
