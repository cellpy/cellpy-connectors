# Issue #2: BatBase MetadataSource adapter (on top of BatBaseClient)

Source: https://github.com/cellpy/cellpy-connectors/issues/2
Labels: enhancement
Captured: 2026-09-26 (Epic M / M2; depends on #1 and jepegit/cellpy#784, both merged)

---

## Context

jepegit/cellpy#784 defines the domain seam for external metadata: a `MetadataSource` Protocol, `MetaRecord`/`MetaQuery` types, and a `cellpy.metadata_sources` entry-point registry, feeding the `MetaResolver` JOURNAL/DB layer. #1 (`BatBaseClient`) is the transport/auth layer that talks to BatBase. This issue is the piece in between: the **BatBase `MetadataSource` adapter** that turns BatBase API responses into `MetaRecord`s.

This corresponds to the "BatBase HTTP adapter" row (row 6) of the #784 work breakdown, placed in this plugin package per #784's placement decision.

## Tasks

- [ ] Implement a `BatBaseMetadataSource` that satisfies the `MetadataSource` Protocol from jepegit/cellpy#784 and is registered under the `cellpy.metadata_sources` entry-point group.
- [ ] Use `BatBaseClient` (#1) for all HTTP/auth; this class holds no credentials and no token logic.
- [ ] `fetch(query) -> tuple[MetaRecord, ...]`: map BatBase JSON → `MetaRecord` drafts (no provenance fields pre-filled — the resolver does that). Unknown key → empty tuple, not an exception.
- [ ] Null-object behaviour: unreachable BatBase (network error, timeout) ⇒ empty layer and a logged warning; the cell still loads. Auth failures (`BatBaseAuthError`) are **not** swallowed — they surface as a clear error, per #784 §3.6.
- [ ] Populate per-source back-link fields (`external_id`, `source_uri`) so `CellMeta.uuid` linkage from #784 row 3 can be established.
- [ ] Decide and implement the first supported `MetaQuery` key(s) (open question in #784: serial? `project`+`sample`? stable external id?). Coordinate with what the BatBase API actually exposes; ife-bat/batbase#391 makes `project` a first-class access concept.
- [ ] Push (`SupportsMetadataPush`) is **out of scope** here; explicit opt-in follow-on, requires `write` scope on the client.
- [ ] Run the `check_metadata_source` conformance kit (#784 row 7) against this adapter, plus a fake in-process HTTP source for offline tests.

## Acceptance criteria

With credentials configured via the connectors configure command (#3), `c.fetch_meta(source="batbase", key=...)` (or the equivalent surface from #784 row 5) returns BatBase metadata as a resolver layer; with BatBase unreachable the same call yields an empty layer and the cell loads; with bad credentials it raises a clear `BatBaseAuthError`. The adapter passes `check_metadata_source`.

## Depends on

- #1 — `BatBaseClient`
- jepegit/cellpy#784 rows 1–3 (Protocol + registry, resolver wiring, `CellMeta.uuid` back-link)
- #3 (indirectly, via #1)

## Related

- ife-bat/batbase#390, ife-bat/batbase#391 (server-side onboarding and project scoping)
- Design doc: `active/cellpy2-metadata-source-integration.md` in cellpy/cellpy-design-and-development


