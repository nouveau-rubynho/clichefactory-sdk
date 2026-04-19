"""Long-document extraction orchestrator.

Flow:

1. Convert the whole file to markdown once (``client.to_markdown_async``).
2. Split the markdown with a ``ChunkStrategy`` (default :class:`TokenChunker`).
3. Fan out per-chunk extractions using ``Cliche.extract_async(text=...)`` with
   ``allow_partial=True`` so a single bad chunk doesn't fail the run.
4. Walk the (JSON-schema-resolved) top-level fields, call each field's
   resolver against the list of per-chunk ``FieldValue`` observations.
5. Finalise via :func:`finalize_extract_result` so the Pydantic model
   coercion + user ``postprocess`` hook runs exactly once on the merged
   dict.

Billing note:
    Every chunk is its own ``extract`` call, so long-doc extraction bills
    per page across all chunks.  The aggregated ``LongExtractionResult.cost``
    exposes a per-chunk breakdown.
"""
from __future__ import annotations

import asyncio
import warnings
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from clichefactory._chunking import ChunkStrategy, TokenChunker
from clichefactory._extract_finalize import finalize_extract_result
from clichefactory._resolvers import default_resolver_for_schema, resolve_resolver
from clichefactory._schema import canonical_schema_to_pydantic
from clichefactory.errors import (
    ConfigurationError,
    ErrorInfo,
    LongExtractionError,
)
from clichefactory.types import (
    Chunk,
    Endpoint,
    FieldValue,
    LongExtractionResult,
    ParsingOptions,
    PartialExtraction,
    Resolver,
    ResolverContext,
    ResolverFn,
    ResolutionTrace,
    ResolverSpec,
)

if TYPE_CHECKING:
    from clichefactory.cliche import Cliche, ExtractionMode


T = TypeVar("T", bound=BaseModel)


# ── Schema introspection ──────────────────────────────────────────────────


def _schema_as_json_schema(schema: type[BaseModel] | dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-schema-shaped dict for the top-level fields of ``schema``."""
    if isinstance(schema, dict):
        if schema.get("type") == "object" and "properties" in schema:
            return schema
        from clichefactory._schema import simple_schema_to_canonical

        return simple_schema_to_canonical(schema)
    try:
        return schema.model_json_schema()
    except Exception:  # defensive — fallback to per-field introspection
        return {"type": "object", "properties": {}}


def _top_level_fields(schema_obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    props = schema_obj.get("properties") or {}
    if isinstance(props, dict):
        return {k: (v if isinstance(v, dict) else {}) for k, v in props.items()}
    return {}


def _dump_to_dict(value: Any) -> dict[str, Any]:
    """Normalise an extract result into a plain dict."""
    if isinstance(value, PartialExtraction):
        return dict(value.raw or {})
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    if isinstance(value, dict):
        return value
    return {}


# ── Orchestrator ──────────────────────────────────────────────────────────


async def extract_long_async(
    cliche: "Cliche[T]",
    *,
    file: str | bytes,
    filename: str | None = None,
    chunker: ChunkStrategy | None = None,
    resolvers: ResolverSpec | None = None,
    default_resolver: Resolver | None = None,
    max_concurrency: int = 4,
    include_chunk_results: bool = False,
    # Mirror Cliche.extract_async knobs so ``extract_long`` is a drop-in.
    mode: "ExtractionMode | None" = None,
    parsing: ParsingOptions | None = None,
    model: Endpoint | None = None,
    ocr_model: Endpoint | None = None,
    include_costs: bool = True,
) -> Any:
    """See :meth:`clichefactory.cliche.Cliche.extract_long_async` for docs."""
    # ── 0. Guardrails ─────────────────────────────────────────────────────
    if file is None:
        raise ConfigurationError(
            ErrorInfo(
                code="long.missing_file",
                message="extract_long requires file=... (a path or bytes).",
            )
        )
    if mode in ("trained", "robust", "robust-trained"):
        raise LongExtractionError(
            ErrorInfo(
                code="long.unsupported_mode",
                message=(
                    f"mode={mode!r} is not supported by extract_long in this SDK release. "
                    "Per-chunk extraction uses the text=... path (BYOK one-shot)."
                ),
                hint="Run extract_long without mode=, or use extract() on a shorter document.",
            )
        )
    if getattr(cliche, "_artifact_id", None):
        raise LongExtractionError(
            ErrorInfo(
                code="long.unsupported_mode",
                message="artifact_id is not supported by extract_long in this SDK release.",
                hint="Trained-artifact long-doc extraction is scheduled for a follow-up release.",
            )
        )

    # ── 1. Resolve chunker & resolver specs ───────────────────────────────
    active_chunker: ChunkStrategy = chunker or TokenChunker()

    merged_resolver_specs: dict[str, Resolver] = {}
    cliche_resolvers = getattr(cliche, "_resolvers", None) or {}
    merged_resolver_specs.update(cliche_resolvers)
    if resolvers:
        merged_resolver_specs.update(resolvers)

    # Validate explicit resolver specs up-front so errors surface before we
    # spend money on chunk extractions.
    resolver_fns: dict[str, ResolverFn] = {}
    for fname, spec in merged_resolver_specs.items():
        resolver_fns[fname] = resolve_resolver(spec, field_name=fname)
    if default_resolver is not None:
        _default_fn: ResolverFn | None = resolve_resolver(default_resolver, field_name="<default>")
    else:
        _default_fn = None

    # ── 2. to_markdown once ───────────────────────────────────────────────
    client = cliche._client  # type: ignore[attr-defined]
    md_doc = await client.to_markdown_async(
        file=file,
        filename=filename,
        parsing=parsing,
    )
    if hasattr(md_doc, "get_markdown"):
        markdown = md_doc.get_markdown() or ""
    else:
        markdown = getattr(md_doc, "markdown", None) or ""
    md_meta = getattr(md_doc, "meta", {}) or {}

    # ── 3. Chunk ──────────────────────────────────────────────────────────
    try:
        chunks = list(await active_chunker.chunks(markdown, md_meta))
    except Exception as e:
        raise LongExtractionError(
            ErrorInfo(
                code="long.chunker_failed",
                message=f"Chunker {type(active_chunker).__name__} raised: {e}",
            )
        ) from e
    if not chunks:
        raise LongExtractionError(
            ErrorInfo(
                code="long.no_chunks",
                message="Chunker produced zero chunks.",
                hint="Check the document is non-empty and the chunker configuration is sane.",
            )
        )

    warnings_list: list[str] = []
    # If the user explicitly picked PageChunker but the markdown had no page
    # markers, our PageChunker falls back to token-based chunking.  Surface
    # that once so they know why page_start/page_end is None.
    from clichefactory._chunking import PageChunker

    if isinstance(active_chunker, PageChunker) and all(
        c.page_start is None for c in chunks
    ):
        warnings_list.append(
            "PageChunker: markdown did not contain page markers; fell back to token-based chunking."
        )

    # ── 4. Per-chunk extraction ──────────────────────────────────────────
    sem = asyncio.Semaphore(max(1, max_concurrency))

    async def _extract_one(chunk: Chunk) -> Any:
        async with sem:
            try:
                return await cliche.extract_async(
                    text=chunk.text,
                    mode=mode,
                    parsing=parsing,
                    model=model,
                    ocr_model=ocr_model,
                    include_costs=include_costs,
                    allow_partial=True,
                )
            except Exception as e:  # treat hard failures as partials
                return _ChunkFailure(error=e, chunk=chunk)

    per_chunk_results: list[Any] = await asyncio.gather(
        *[_extract_one(c) for c in chunks]
    )

    successes = [r for r in per_chunk_results if not isinstance(r, _ChunkFailure)]
    if not successes:
        failures = [r for r in per_chunk_results if isinstance(r, _ChunkFailure)]
        first_err = failures[0].error if failures else RuntimeError("no chunks")
        raise LongExtractionError(
            ErrorInfo(
                code="long.all_chunks_failed",
                message=(
                    f"All {len(chunks)} chunk extractions failed. "
                    f"First error: {first_err!s}"
                ),
            )
        ) from first_err
    if len(successes) < len(chunks):
        warnings_list.append(
            f"{len(chunks) - len(successes)} of {len(chunks)} chunk extractions failed; "
            "their fields will be treated as missing."
        )

    # ── 5. Collect per-field values ──────────────────────────────────────
    schema_obj = _schema_as_json_schema(cliche._schema)  # type: ignore[attr-defined]
    top_fields = _top_level_fields(schema_obj)

    # Ensure every field in the schema is visited even if no chunk produced it.
    per_field: dict[str, list[FieldValue]] = {fname: [] for fname in top_fields}

    for chunk, result in zip(chunks, per_chunk_results):
        if isinstance(result, _ChunkFailure):
            result_dict: dict[str, Any] = {}
        else:
            result_dict = _dump_to_dict(result)
        for fname in top_fields:
            raw_val = result_dict.get(fname)
            per_field[fname].append(
                FieldValue(value=raw_val, chunk=chunk, confidence=None)
            )
    # Also surface any extra keys the LLM emitted that are not in the schema
    # (rare — happens with ``extra="allow"`` models).  Don't add new entries
    # if a key wasn't declared; resolvers would have no schema to work with.

    # ── 6. Resolve each field ────────────────────────────────────────────
    resolutions: dict[str, ResolutionTrace] = {}
    merged: dict[str, Any] = {}
    all_chunks_tuple = tuple(chunks)

    for fname, field_schema in top_fields.items():
        values = per_field[fname]
        ctx = ResolverContext(
            field_name=fname,
            field_schema=field_schema,
            all_chunks=all_chunks_tuple,
        )
        resolver_fn = resolver_fns.get(fname)
        resolver_name: str
        field_warnings: list[str] = []

        if resolver_fn is None and _default_fn is not None:
            resolver_fn = _default_fn
            resolver_name = getattr(_default_fn, "__name__", "default")
        elif resolver_fn is None:
            resolver_fn, resolver_name, warn_template = default_resolver_for_schema(field_schema)
            if warn_template:
                msg = warn_template % fname
                field_warnings.append(msg)
                warnings_list.append(f"field {fname!r}: {msg}")
                warnings.warn(
                    f"[clichefactory.extract_long] field {fname!r}: {msg}",
                    UserWarning,
                    stacklevel=3,
                )
        else:
            resolver_name = getattr(resolver_fn, "__cf_resolver_name__", None) or getattr(
                resolver_fn, "__name__", "custom"
            )

        try:
            final_value = resolver_fn(values, ctx)
        except Exception as e:
            raise LongExtractionError(
                ErrorInfo(
                    code="long.resolver_failed",
                    message=f"Resolver {resolver_name!r} for field {fname!r} raised: {e}",
                )
            ) from e

        winning_indices = _winning_chunk_indices(values, final_value)

        resolutions[fname] = ResolutionTrace(
            field_name=fname,
            resolver_name=resolver_name,
            per_chunk_values=tuple(values),
            winning_chunk_indices=winning_indices,
            final_value=final_value,
            warnings=tuple(field_warnings),
        )
        merged[fname] = final_value

    # ── 7. Finalise through the single coerce→postprocess→validate path ──
    validated_or_partial = finalize_extract_result(
        merged,
        cliche._schema,  # type: ignore[attr-defined]
        getattr(cliche, "_postprocess", None),
        allow_partial=False,
        validation_errors=None,
        response_status=None,
    )

    if not include_chunk_results:
        return validated_or_partial

    cost = _aggregate_cost(per_chunk_results)

    return LongExtractionResult(
        value=validated_or_partial,
        chunks=all_chunks_tuple,
        per_chunk=tuple(per_chunk_results),
        per_field={k: tuple(v) for k, v in per_field.items()},
        resolutions=resolutions,
        warnings=tuple(warnings_list),
        cost=cost,
    )


# ── Helpers ───────────────────────────────────────────────────────────────


def _winning_chunk_indices(values: list[FieldValue], final_value: Any) -> tuple[int, ...]:
    """Best-effort: which chunk(s) contributed the winning value.

    For scalar finals, returns chunks whose value equals the final value.
    For collection finals, returns every chunk that contributed a non-empty
    value (they all had a hand in the concatenation).
    """
    if isinstance(final_value, list):
        return tuple(fv.chunk.index for fv in values if not _is_missing(fv.value))
    out: list[int] = []
    for fv in values:
        try:
            if fv.value == final_value:
                out.append(fv.chunk.index)
        except Exception:
            continue
    return tuple(out)


def _is_missing(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, (list, tuple, set, dict, str)) and len(v) == 0:
        return True
    return False


class _ChunkFailure:
    """Internal sentinel for a per-chunk extraction that raised."""

    __slots__ = ("error", "chunk")

    def __init__(self, error: BaseException, chunk: Chunk) -> None:
        self.error = error
        self.chunk = chunk

    @property
    def raw_or_none(self) -> dict[str, Any] | None:
        return None


def _aggregate_cost(per_chunk_results: list[Any]) -> dict[str, Any]:
    """Merge per-chunk cost dicts into a summary.  Best-effort — cost shape
    varies by provider, so we only aggregate numeric totals we recognise."""
    total_usd = 0.0
    saw_usd = False
    by_chunk: list[dict[str, Any]] = []
    for i, r in enumerate(per_chunk_results):
        if isinstance(r, _ChunkFailure):
            by_chunk.append({"chunk": i, "error": str(r.error)})
            continue
        cost_obj: Any = None
        if isinstance(r, BaseModel):
            cost_obj = getattr(r, "costs", None) or getattr(r, "cost", None)
        elif isinstance(r, PartialExtraction):
            cost_obj = None
        elif isinstance(r, dict):
            cost_obj = r.get("costs") or r.get("cost")
        # Best-effort pick of total USD
        chunk_cost: dict[str, Any] = {"chunk": i}
        if cost_obj is not None:
            if hasattr(cost_obj, "model_dump"):
                cost_dict = cost_obj.model_dump()
            elif isinstance(cost_obj, dict):
                cost_dict = cost_obj
            else:
                cost_dict = {}
            val = cost_dict.get("total_usd")
            if isinstance(val, (int, float)):
                total_usd += float(val)
                saw_usd = True
                chunk_cost["total_usd"] = val
        by_chunk.append(chunk_cost)
    out: dict[str, Any] = {"by_chunk": by_chunk, "num_chunks": len(per_chunk_results)}
    if saw_usd:
        out["total_usd"] = total_usd
    return out
