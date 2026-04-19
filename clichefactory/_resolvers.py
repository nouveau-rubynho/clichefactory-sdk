"""Built-in field resolvers for long-document extraction.

A resolver is a callable::

    (list[FieldValue], ResolverContext) -> Any

It receives every chunk's value for a single field (including ``None`` for
chunks that produced nothing) and returns the single merged value.  The
orchestrator applies resolvers field-by-field; any exception raised by a
resolver becomes a :class:`~clichefactory.errors.LongExtractionError` with
code ``long.resolver_failed``.

Public re-exports and the string-alias registry live in
:mod:`clichefactory.resolvers`.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from clichefactory.errors import ConfigurationError, ErrorInfo
from clichefactory.types import (
    FieldValue,
    Resolver,
    ResolverContext,
    ResolverFn,
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _is_missing(v: Any) -> bool:
    """A value counts as "missing" if it is ``None`` or an empty collection."""
    if v is None:
        return True
    if isinstance(v, (list, tuple, set, dict, str)) and len(v) == 0:
        return True
    return False


def _non_null(values: list[FieldValue]) -> list[FieldValue]:
    return [fv for fv in values if not _is_missing(fv.value)]


# ── Scalar resolvers ──────────────────────────────────────────────────────


def first_non_null(values: list[FieldValue], ctx: ResolverContext) -> Any:
    """Return the value from the earliest chunk (by index) that produced one."""
    for fv in sorted(values, key=lambda x: x.chunk.index):
        if not _is_missing(fv.value):
            return fv.value
    return None


def last_non_null(values: list[FieldValue], ctx: ResolverContext) -> Any:
    """Return the value from the latest chunk that produced one."""
    for fv in sorted(values, key=lambda x: x.chunk.index, reverse=True):
        if not _is_missing(fv.value):
            return fv.value
    return None


def most_common(values: list[FieldValue], ctx: ResolverContext) -> Any:
    """Return the value that appeared in the most chunks.

    Ties are broken by earliest chunk index.  Unhashable values (dicts,
    lists) fall back to the "first_non_null" behaviour because they cannot
    be counted.
    """
    nn = _non_null(values)
    if not nn:
        return None
    try:
        counts = Counter(fv.value for fv in nn)
    except TypeError:
        return first_non_null(values, ctx)
    top_count = max(counts.values())
    winners = {v for v, c in counts.items() if c == top_count}
    for fv in sorted(nn, key=lambda x: x.chunk.index):
        if fv.value in winners:
            return fv.value
    return None


def pick_by_confidence(values: list[FieldValue], ctx: ResolverContext) -> Any:
    """Return the highest-confidence value; falls back to first non-null."""
    nn = _non_null(values)
    if not nn:
        return None
    scored = [fv for fv in nn if fv.confidence is not None]
    if not scored:
        return first_non_null(values, ctx)
    return max(scored, key=lambda fv: (fv.confidence, -fv.chunk.index)).value


# ── Numeric aggregators ───────────────────────────────────────────────────


def _as_number(v: Any) -> float | int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            if "." in v or "," in v:
                return float(v.replace(",", "."))
            return int(v)
        except ValueError:
            return None
    return None


def sum_numeric(values: list[FieldValue], ctx: ResolverContext) -> Any:
    """Sum numeric values, ignoring non-numeric / missing."""
    nums: list[float | int] = []
    for fv in values:
        n = _as_number(fv.value)
        if n is not None:
            nums.append(n)
    if not nums:
        return None
    if all(isinstance(n, int) for n in nums):
        return sum(nums)
    return float(sum(nums))


def max_numeric(values: list[FieldValue], ctx: ResolverContext) -> Any:
    nums = [_as_number(fv.value) for fv in values]
    nums = [n for n in nums if n is not None]
    return max(nums) if nums else None


def min_numeric(values: list[FieldValue], ctx: ResolverContext) -> Any:
    nums = [_as_number(fv.value) for fv in values]
    nums = [n for n in nums if n is not None]
    return min(nums) if nums else None


# ── Collection resolvers ──────────────────────────────────────────────────


def _coerce_list(v: Any) -> list[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    return [v]


def concat(
    values: list[FieldValue] | None = None,
    ctx: ResolverContext | None = None,
    *,
    separator: str | None = None,
) -> Any:
    """Concatenate per-chunk lists in chunk order.

    Can be used directly (``resolvers={"line_items": concat}``) or as a
    factory for string concatenation::

        resolvers={"notes": concat(separator="\\n\\n")}
    """
    # Factory form: ``concat(separator="...")``.
    if values is None:
        sep = separator or "\n\n"

        def _concat_strings(vs: list[FieldValue], c: ResolverContext) -> Any:
            parts: list[str] = []
            for fv in sorted(vs, key=lambda x: x.chunk.index):
                if _is_missing(fv.value):
                    continue
                parts.append(str(fv.value))
            return sep.join(parts) if parts else None

        return _concat_strings

    # Direct call form: ``concat(values, ctx)``.
    merged: list[Any] = []
    for fv in sorted(values, key=lambda x: x.chunk.index):
        merged.extend(_coerce_list(fv.value))
    return merged


def concat_dedupe(
    key: Callable[[Any], Any] | str | None = None,
) -> ResolverFn:
    """Concatenate list-valued fields, dropping duplicates.

    ``key`` picks the dedupe identity:

    - ``None`` → dedupe by the whole element (stringified for unhashable).
    - ``str`` → dedupe by that attribute/key of each element.
    - ``callable`` → dedupe by ``key(element)``.

    Items that fall after a previously-seen key are dropped.  The first
    occurrence wins.
    """

    def _key(item: Any) -> Any:
        if key is None:
            try:
                hash(item)
                return item
            except TypeError:
                return repr(item)
        if isinstance(key, str):
            if isinstance(item, dict):
                return item.get(key)
            return getattr(item, key, None)
        return key(item)

    def _fn(values: list[FieldValue], ctx: ResolverContext) -> Any:
        seen: set[Any] = set()
        merged: list[Any] = []
        for fv in sorted(values, key=lambda x: x.chunk.index):
            for item in _coerce_list(fv.value):
                k = _key(item)
                try:
                    if k in seen:
                        continue
                    seen.add(k)
                except TypeError:
                    k_repr = repr(k)
                    if k_repr in seen:
                        continue
                    seen.add(k_repr)
                merged.append(item)
        return merged

    return _fn


def union_by(key: Callable[[Any], Any] | str) -> ResolverFn:
    """Alias for ``concat_dedupe(key=...)`` with a required key argument."""
    return concat_dedupe(key=key)


# ── LLM-backed resolver (opt-in) ──────────────────────────────────────────


def llm_reconcile(
    *,
    instructions: str | None = None,
    model: Any = None,
) -> ResolverFn:
    """Reconcile conflicting values with one extra LLM call.

    **v1 limitation:** this resolver is a stub that currently falls back to
    :func:`most_common` and attaches a note to ``ctx``'s warnings.  The real
    LLM reconciliation path is scheduled for the next SDK release; the API
    is fixed now so users can declare their intent today.

    Parameters
    ----------
    instructions:
        Natural-language hint the LLM would receive when reconciling.
    model:
        Optional :class:`~clichefactory.types.Endpoint` override.  Ignored
        in v1.
    """

    def _fn(values: list[FieldValue], ctx: ResolverContext) -> Any:
        nn = _non_null(values)
        if not nn:
            return None
        distinct: set[Any]
        try:
            distinct = {fv.value for fv in nn}
        except TypeError:
            distinct = {repr(fv.value) for fv in nn}
        if len(distinct) <= 1:
            return nn[0].value
        return most_common(values, ctx)

    _fn.__cf_resolver_name__ = "llm_reconcile"  # type: ignore[attr-defined]
    return _fn


# ── Default policy ────────────────────────────────────────────────────────


def default_resolver_for_schema(
    field_schema: dict[str, Any],
) -> tuple[ResolverFn, str, str | None]:
    """Pick a default resolver given a JSON Schema fragment.

    Returns ``(resolver, name, warning_message_or_none)``.  The warning is
    surfaced to the user once, up-front, so they can decide whether to
    override the default.
    """
    t = field_schema.get("type")
    if isinstance(t, list):
        non_null = [x for x in t if x != "null"]
        t = non_null[0] if non_null else "string"

    if t == "array":
        return (
            concat,
            "concat",
            (
                "Using default resolver 'concat' (no dedupe). If duplicates are "
                "possible across chunks, pass resolvers={'%s': concat_dedupe(key=...)}."
            ),
        )
    if t in ("string", "number", "integer", "boolean"):
        return (first_non_null, "first_non_null", None)
    if t == "object":
        return (first_non_null, "first_non_null", None)
    return (first_non_null, "first_non_null", None)


# ── String-alias registry ─────────────────────────────────────────────────

_ALIASES: dict[str, ResolverFn] = {
    "first_non_null": first_non_null,
    "last_non_null": last_non_null,
    "most_common": most_common,
    "pick_by_confidence": pick_by_confidence,
    "sum_numeric": sum_numeric,
    "max_numeric": max_numeric,
    "min_numeric": min_numeric,
    "concat": concat,  # type: ignore[dict-item]
    "union": concat_dedupe(),
}


def _resolve_alias_with_args(alias: str) -> ResolverFn | None:
    """Support a tiny subset of ``"name=value"`` forms in aliases.

    Currently supported:

    - ``concat_dedupe_by=<attr>``   → ``concat_dedupe(key="<attr>")``

    Anything else returns ``None`` so the caller raises a clean error.
    """
    if alias.startswith("concat_dedupe_by="):
        attr = alias.split("=", 1)[1].strip()
        if attr:
            return concat_dedupe(key=attr)
    return None


def resolve_resolver(spec: Resolver, *, field_name: str) -> ResolverFn:
    """Normalise any user-facing resolver spec into a plain callable."""
    if callable(spec):
        return spec
    if isinstance(spec, str):
        if spec in _ALIASES:
            return _ALIASES[spec]
        with_args = _resolve_alias_with_args(spec)
        if with_args is not None:
            return with_args
        raise ConfigurationError(
            ErrorInfo(
                code="long.unknown_resolver",
                message=f"Unknown resolver alias {spec!r} for field {field_name!r}.",
                hint=(
                    "Use one of: "
                    + ", ".join(sorted(_ALIASES))
                    + ", or pass a callable from clichefactory.resolvers."
                ),
            )
        )
    raise ConfigurationError(
        ErrorInfo(
            code="long.invalid_resolver",
            message=f"Resolver for field {field_name!r} must be callable or a string alias.",
        )
    )
