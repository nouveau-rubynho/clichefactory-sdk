"""Public field resolvers for :meth:`clichefactory.Cliche.extract_long`.

A resolver merges per-chunk values for a single schema field into one final
value.  Resolvers are scoped per-field::

    from clichefactory.resolvers import (
        concat_dedupe, first_non_null, last_non_null, llm_reconcile,
    )

    cliche = client.cliche(
        Invoice,
        resolvers={
            "invoice_number": first_non_null,
            "total":          last_non_null,
            "line_items":     concat_dedupe(key=lambda it: (it["description"], it["amount"])),
            "notes":          "concat",
        },
    )

String aliases are supported for config-driven use cases (YAML/JSON)::

    resolvers = {
        "invoice_number": "first_non_null",
        "line_items":     "concat_dedupe_by=line_id",
    }

Custom callables follow the signature
``(list[FieldValue], ResolverContext) -> Any``.  See
:mod:`clichefactory.types`.
"""
from __future__ import annotations

from clichefactory._resolvers import (
    concat,
    concat_dedupe,
    first_non_null,
    last_non_null,
    llm_reconcile,
    max_numeric,
    min_numeric,
    most_common,
    pick_by_confidence,
    sum_numeric,
    union_by,
)

__all__ = [
    "concat",
    "concat_dedupe",
    "first_non_null",
    "last_non_null",
    "llm_reconcile",
    "max_numeric",
    "min_numeric",
    "most_common",
    "pick_by_confidence",
    "sum_numeric",
    "union_by",
]
