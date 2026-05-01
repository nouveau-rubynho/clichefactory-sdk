# Changelog

All notable changes to `clichefactory` are documented in this file.

## [0.3.0] — 2026-05-01

### Added

- **Automatic retries on transient service errors.** Service-mode HTTP
  callsites (`extract`, `to_markdown`, presigned upload, presigned PUT)
  now retry on connection / read errors and on `408`, `425`, `429`,
  `500`, `502`, `503`, `504` responses. Bounded at 4 attempts with
  full-jitter exponential backoff (max 8 s per sleep). When the server
  sends `Retry-After` (e.g. when rate-limited), the SDK honors it,
  clamped to 30 s so a misbehaving upstream can't park a request
  indefinitely. Non-retryable 4xx responses (auth, validation,
  not-found) still fail fast as before.
- **Idempotency keys on retries.** `extract` already derived an
  idempotency key from the request payload and sent it inside the
  canonical envelope; the same key is now reused on every retry so the
  server replays the cached response instead of double-billing. The
  `to_markdown` and presigned-upload requests now also derive a stable
  key and send it as the `Idempotency-Key` HTTP header. The presigned
  S3 PUT itself is naturally idempotent on URL+content, so no key is
  required there — retries just cover transport hiccups.

### Notes for consumers

- No public API changed. The retry / idempotency wiring is internal to
  the service-mode transport layer; existing call sites get the new
  behavior automatically on upgrade.
- Users wanting to pin their own idempotency key (today the SDK derives
  one from the request body) — that knob is still deferred until a real
  trigger surfaces.

## [0.2.2] — 2026-04-29

### Fixed
- **OpenAI client**: switched from `max_tokens` to `max_completion_tokens` for
  compatibility with newer OpenAI models (GPT-5.x, o-series) that reject the
  legacy parameter. Reasoning models (o1/o3/o4 prefixes) now also have
  `temperature` omitted, since they reject it.
- **Anthropic client**: structured output schemas now have
  `additionalProperties: false` recursively applied to all object nodes,
  required by the Anthropic Messages API for `json_schema` outputs.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(pre-1.0: minor bumps may introduce additive public API, patch bumps are
bugfix/docs only).

## [0.2.0] — 2026-04-19

Long-document extraction: chunk a document, extract per chunk, merge results
into a single Pydantic model. Purely additive; no changes to existing APIs.

### Added

- **`Cliche.extract_long` / `extract_long_async`** — new top-level entry point
  for documents that exceed the single-call LLM context window (typically
  longer than ~20 pages). Runs `to_markdown` once, chunks the markdown,
  extracts each chunk in parallel via the existing `extract(text=...)` path,
  and merges per-field using a configurable resolver.
- **`clichefactory.chunking`** — public chunking strategies:
  - `TokenChunker` (default) — token-budgeted splits with configurable overlap.
  - `PageChunker` — splits on markdown page markers; falls back to
    `TokenChunker` when the document has no detectable page breaks (emits a
    warning so the fallback is visible).
  - `HeadingChunker` — splits on markdown headings, re-chunking oversize
    sections with `TokenChunker`.
  - `ChunkStrategy` protocol for custom chunkers.
- **`clichefactory.resolvers`** — built-in per-field merge strategies:
  - Scalar: `first_non_null`, `last_non_null`, `most_common`,
    `pick_by_confidence`.
  - Numeric: `sum_numeric`, `max_numeric`, `min_numeric`.
  - Collection: `concat`, `concat_dedupe`, `union_by`.
  - `llm_reconcile` — v1 stub; currently falls back to `most_common`, full
    LLM-driven reconciliation planned for a subsequent release.
  - String aliases (`"first_non_null"`, `"concat_dedupe"`,
    `"concat_dedupe_by=invoice_number"`, …) for config-driven setups.
- **`resolvers=` keyword** on `Client.cliche()` and `Cliche(...)` — mirrors
  the existing `postprocess` hook, so per-field merge rules can be set
  once at the cliche level and overridden per `extract_long` call.
- **Default resolver policy** — driven by the target Pydantic model's JSON
  schema: arrays → `concat` with a **loud warning** recommending
  `concat_dedupe` or `concat_dedupe_by=<attr>`; scalars / objects →
  `first_non_null`.
- **New public types**: `Chunk`, `FieldValue`, `ResolverContext`,
  `Resolver`, `ResolverFn`, `ResolverSpec`, `ResolutionTrace`,
  `LongExtractionResult` (returned when `include_chunk_results=True`,
  exposing per-chunk results, per-field values, resolution traces,
  warnings and aggregated cost).
- **New exception**: `LongExtractionError` with a code taxonomy:
  `long.chunker_failed`, `long.no_chunks`, `long.all_chunks_failed`,
  `long.resolver_failed`, `long.unsupported_mode`,
  `long.unknown_resolver`, `long.invalid_resolver`.
- **README**: new "Long documents (chunk + merge)" section with usage,
  chunker and resolver tables, default-policy explanation, and the debug
  surface of `LongExtractionResult`.
- **Tests**: 52 new unit tests covering resolvers, chunkers, default policy,
  and end-to-end orchestration with mocked `to_markdown` / `extract`.

### Limitations (v1)

- `extract_long` only runs the BYOK one-shot `extract(text=...)` path per
  chunk. `mode="trained" | "robust" | "robust-trained"` and `artifact_id=`
  are explicitly rejected with `LongExtractionError("long.unsupported_mode")`
  until we add per-chunk support for them.
- `llm_reconcile` is a stub (see above).
- No server-side `extraction_mode="long"` yet — this release is SDK-only.
  A server implementation will be considered once Emio UI demand validates
  the resolver patterns.

## [0.1.0] — 2026-04-12

- Initial public release.
