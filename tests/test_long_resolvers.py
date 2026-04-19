"""Unit tests for built-in resolvers (no network, no LLM)."""
from __future__ import annotations

import pytest

from clichefactory.resolvers import (
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
from clichefactory._resolvers import (
    default_resolver_for_schema,
    resolve_resolver,
)
from clichefactory.errors import ConfigurationError
from clichefactory.types import Chunk, FieldValue, ResolverContext


def _ctx(field_name: str = "f", schema: dict | None = None, chunks: tuple[Chunk, ...] = ()) -> ResolverContext:
    return ResolverContext(field_name=field_name, field_schema=schema or {}, all_chunks=chunks)


def _fv(value, idx: int = 0, conf: float | None = None) -> FieldValue:
    return FieldValue(value=value, chunk=Chunk(index=idx, text=""), confidence=conf)


# ── Scalars ───────────────────────────────────────────────────────────────


def test_first_non_null_skips_missing():
    values = [_fv(None, 0), _fv("", 1), _fv("A", 2), _fv("B", 3)]
    assert first_non_null(values, _ctx()) == "A"


def test_first_non_null_all_missing_returns_none():
    assert first_non_null([_fv(None, 0), _fv(None, 1)], _ctx()) is None


def test_last_non_null_picks_latest_chunk():
    values = [_fv("A", 0), _fv("B", 2), _fv(None, 3)]
    assert last_non_null(values, _ctx()) == "B"


def test_most_common_hashable():
    values = [_fv("A", 0), _fv("B", 1), _fv("A", 2), _fv("C", 3)]
    assert most_common(values, _ctx()) == "A"


def test_most_common_ties_prefer_earliest():
    values = [_fv("B", 0), _fv("A", 1)]
    # Each appears once — ties broken by earliest chunk index.
    assert most_common(values, _ctx()) == "B"


def test_most_common_unhashable_falls_back():
    values = [_fv({"x": 1}, 0), _fv({"x": 2}, 1)]
    assert most_common(values, _ctx()) == {"x": 1}


def test_pick_by_confidence_uses_highest():
    values = [_fv("A", 0, conf=0.2), _fv("B", 1, conf=0.9), _fv("C", 2, conf=0.5)]
    assert pick_by_confidence(values, _ctx()) == "B"


def test_pick_by_confidence_no_scores_falls_back_to_first_non_null():
    values = [_fv(None, 0), _fv("A", 1), _fv("B", 2)]
    assert pick_by_confidence(values, _ctx()) == "A"


# ── Numeric aggregators ───────────────────────────────────────────────────


def test_sum_numeric_mixed():
    values = [_fv(1, 0), _fv("2.5", 1), _fv(None, 2), _fv("not a number", 3), _fv(3, 4)]
    assert sum_numeric(values, _ctx()) == pytest.approx(6.5)


def test_sum_numeric_all_int_preserves_int():
    assert sum_numeric([_fv(1, 0), _fv(2, 1), _fv(3, 2)], _ctx()) == 6
    assert isinstance(sum_numeric([_fv(1, 0), _fv(2, 1)], _ctx()), int)


def test_max_min_numeric():
    values = [_fv("10", 0), _fv(3, 1), _fv(7.5, 2), _fv(None, 3)]
    assert max_numeric(values, _ctx()) == 10
    assert min_numeric(values, _ctx()) == 3


def test_sum_numeric_ignores_bools():
    # bool is a subclass of int in Python; our coercion ignores it.
    assert sum_numeric([_fv(True, 0), _fv(1, 1)], _ctx()) == 1


# ── Collections ───────────────────────────────────────────────────────────


def test_concat_direct_call_joins_lists_in_order():
    values = [_fv([1, 2], 1), _fv([3], 0), _fv(None, 2), _fv([4], 3)]
    # Sorted by chunk index: [3], [1,2], None, [4]
    assert concat(values, _ctx()) == [3, 1, 2, 4]


def test_concat_factory_joins_strings():
    resolver = concat(separator=" | ")
    values = [_fv("b", 1), _fv("a", 0), _fv(None, 2), _fv("", 3)]
    assert resolver(values, _ctx()) == "a | b"


def test_concat_dedupe_by_callable():
    resolver = concat_dedupe(key=lambda x: x["id"])
    values = [
        _fv([{"id": 1, "v": "a"}, {"id": 2, "v": "b"}], 0),
        _fv([{"id": 2, "v": "b2"}, {"id": 3, "v": "c"}], 1),
    ]
    out = resolver(values, _ctx())
    assert [x["id"] for x in out] == [1, 2, 3]
    # First occurrence wins.
    assert out[1]["v"] == "b"


def test_concat_dedupe_by_string_key():
    resolver = concat_dedupe(key="sku")
    values = [
        _fv([{"sku": "a"}, {"sku": "b"}], 0),
        _fv([{"sku": "a"}, {"sku": "c"}], 1),
    ]
    out = resolver(values, _ctx())
    assert [x["sku"] for x in out] == ["a", "b", "c"]


def test_concat_dedupe_default_key_on_scalars():
    resolver = concat_dedupe()
    values = [_fv([1, 2, 3], 0), _fv([2, 3, 4], 1)]
    assert resolver(values, _ctx()) == [1, 2, 3, 4]


def test_union_by_is_alias():
    a = concat_dedupe(key="id")
    b = union_by("id")
    values = [_fv([{"id": 1}, {"id": 2}], 0), _fv([{"id": 2}, {"id": 3}], 1)]
    assert a(values, _ctx()) == b(values, _ctx())


def test_concat_coerces_scalar_to_single_element_list():
    # Sometimes a chunk returns a scalar where we expected a list.
    values = [_fv("lonely", 0), _fv(["a", "b"], 1)]
    assert concat(values, _ctx()) == ["lonely", "a", "b"]


# ── llm_reconcile v1 stub behaviour ───────────────────────────────────────


def test_llm_reconcile_stub_falls_back_to_most_common():
    resolver = llm_reconcile(instructions="pick the right one")
    values = [_fv("A", 0), _fv("B", 1), _fv("A", 2)]
    assert resolver(values, _ctx()) == "A"


def test_llm_reconcile_unanimous_returns_that_value():
    resolver = llm_reconcile()
    values = [_fv("same", 0), _fv("same", 1)]
    assert resolver(values, _ctx()) == "same"


def test_llm_reconcile_carries_name_marker():
    resolver = llm_reconcile()
    assert getattr(resolver, "__cf_resolver_name__", None) == "llm_reconcile"


# ── Default policy ───────────────────────────────────────────────────────


def test_default_for_array_is_concat_with_warning():
    fn, name, warn = default_resolver_for_schema({"type": "array"})
    assert name == "concat"
    assert warn is not None  # warning template present
    assert "%s" in warn  # parametrised on the field name


def test_default_for_string_is_first_non_null_no_warning():
    fn, name, warn = default_resolver_for_schema({"type": "string"})
    assert name == "first_non_null"
    assert warn is None


def test_default_for_nullable_type_list():
    fn, name, warn = default_resolver_for_schema({"type": ["string", "null"]})
    assert name == "first_non_null"


# ── Alias registry ───────────────────────────────────────────────────────


def test_resolve_alias_by_name():
    fn = resolve_resolver("first_non_null", field_name="x")
    assert fn is first_non_null


def test_resolve_concat_dedupe_by_attr_alias():
    fn = resolve_resolver("concat_dedupe_by=line_id", field_name="line_items")
    values = [
        _fv([{"line_id": "a"}, {"line_id": "b"}], 0),
        _fv([{"line_id": "a"}, {"line_id": "c"}], 1),
    ]
    out = fn(values, _ctx())
    assert [x["line_id"] for x in out] == ["a", "b", "c"]


def test_resolve_unknown_alias_raises_configuration_error():
    with pytest.raises(ConfigurationError) as exc:
        resolve_resolver("not_a_real_resolver", field_name="x")
    assert exc.value.info.code == "long.unknown_resolver"


def test_resolve_non_callable_non_string_raises():
    with pytest.raises(ConfigurationError) as exc:
        resolve_resolver(123, field_name="x")  # type: ignore[arg-type]
    assert exc.value.info.code == "long.invalid_resolver"


def test_resolve_callable_passes_through():
    def my_resolver(values, ctx):
        return "hi"

    assert resolve_resolver(my_resolver, field_name="x") is my_resolver
