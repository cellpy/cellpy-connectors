# Issue #1: Implement BatBaseClient (OAuth2 client-credentials)

- GitHub: https://github.com/cellpy/cellpy-connectors/issues/1
- Labels: yolo, enhancement
- Epic: jepegit/cellpy#783 Epic M, M0

## Original description

## Context

First concrete connector, built on the shared connector base in #3. This is the **transport/auth layer** only: it knows about `/o/token/`, bearer tokens and BatBase's REST endpoints. The `MetadataSource` adapter from jepegit/cellpy#784 (mapping BatBase JSON → `MetaRecord`, null-object degradation when offline) sits on top of it and is tracked in #2.

Talks to BatBase's `/o/token/` (django-oauth-toolkit, OAuth2 client-credentials grant) and BatBase's DRF API using `Authorization: Bearer`.

On the BatBase side, client-credentials tokens are bound to the owning user of the OAuth2 `Application` (ife-bat/batbase#387), so `request.user` is a real user. Scopes in use: `read`, `write`, `groups`.

## Tasks

- [ ] Implement the client-credentials token fetch: `POST /o/token/` with `grant_type=client_credentials` and `scope`, using client_id/secret as HTTP Basic auth (consistent with the reference implementation in BatBase's `scripts/get_bearer_token.py`).
- [ ] Cache the access token in memory with its expiry (`expires_in`); there is no refresh token in this grant type, so re-fetch a fresh token on expiry rather than trying to refresh.
- [ ] On a 401 mid-session (token revoked, or the Application secret was rotated via BatBase's admin rotate-secret action), re-authenticate once and retry the request before surfacing an error.
- [ ] Store client_id/client_secret via the OS keyring (dedicated service name), using the credential resolver from #3, with environment variables (`CELLPY_BATBASE_CLIENT_ID` / `CELLPY_BATBASE_CLIENT_SECRET`) as a fallback for CI/HPC/headless environments where no OS keyring is available. No config-file storage of secrets (rejected in jepegit/cellpy#784).
- [ ] Plug into the generic `configure <connector>` CLI from #3 (exact command shape decided there, e.g. `cellpy connectors configure batbase`) to collect and store the client_id/secret.
- [ ] Default to `scope="read"`; make `write` scope opt-in/explicit rather than requesting `read write` by default, since not all users need write access.
- [ ] Raise a specific, clearly worded exception (e.g. `BatBaseAuthError`, subclassing `ConnectorAuthError` from #3) for "no credentials configured" and "credentials rejected" cases, distinct from generic `requests.HTTPError`, so failures are debuggable by a scientist running a script rather than reading a stack trace.
- [ ] Document the onboarding flow: create an Application at BatBase's `/o/applications/` (once available — see ife-bat/batbase#390), then run the configure command locally.

## Acceptance criteria

A user who has created a BatBase Application can run the configure command once, and afterwards a call like `cellpy.batbase.get_dataset(...)` works transparently — including across process restarts and token expiry — without the user handling tokens directly.

## Related

- Parent design: jepegit/cellpy#784 — this issue is the auth/transport part of its "BatBase HTTP adapter" row; note #784's design doc assumed a static token, whereas BatBase issues short-lived client-credentials tokens (hence the caching/expiry/401 tasks above).
- Follow-on: #2 (`MetadataSource` adapter on top of this client).
- Depends on: #3 (shared connector base: credential resolution, `ApiClientBase`, configure CLI)
- Depends on: ife-bat/batbase#390 (self-service `/o/applications/` for end users)
- Row-level access on the server side is handled separately in ife-bat/batbase#391 (project-scoped access control); this client does not need to know about it.


