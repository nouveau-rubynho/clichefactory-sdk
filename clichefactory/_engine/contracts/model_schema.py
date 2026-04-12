"""
Canonical model_schema: JSON Schema validation, BatchConfig -> canonical converter,
and canonical JSON Schema -> Pydantic model builder.
"""
from __future__ import annotations

import re
from typing import Any, Type

import jsonschema
from pydantic import BaseModel, create_model

# JSON Schema draft 2020-12 meta-schema for validation
_DRAFT_2020_12_META = "https://json-schema.org/draft/2020-12/schema"
# Fallback: accept any object with at least "type" or "$schema" for loose validation
_LOOSE_REQUIRED_KEYS = frozenset({"type", "$schema"})


def validate_model_schema(schema: dict[str, Any]) -> None:
    """
    Validate that schema is valid JSON Schema. Raises jsonschema.SchemaError or
    jsonschema.ValidationError if invalid.
    """
    if not isinstance(schema, dict):
        raise TypeError("model_schema must be a dict")
    if not _LOOSE_REQUIRED_KEYS.intersection(schema.keys()) and "properties" not in schema:
        raise jsonschema.SchemaError("Schema must have 'type', '$schema', or 'properties'")
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError:
        jsonschema.Draft7Validator.check_schema(schema)


def _batch_field_type_to_json_schema(field: dict[str, Any]) -> dict[str, Any]:
    """Convert Emio FieldDefinition type to JSON Schema property."""
    ft = field.get("type") or field.get("type_")
    if isinstance(ft, dict):
        return ft
    t = (ft or "text").lower() if isinstance(ft, str) else "string"
    if t in ("text", "string"):
        return {"type": "string"}
    if t == "integer":
        return {"type": "integer"}
    if t in ("float", "number"):
        return {"type": "number"}
    if t == "date":
        return {"type": "string", "format": "date"}
    if t == "list_of_models":
        target = field.get("target_model")
        if not target:
            raise ValueError("list_of_models requires target_model")
        return {"type": "array", "items": {"$ref": f"#/$defs/{target}"}}
    return {"type": "string"}


def batch_config_to_canonical(config: dict[str, Any]) -> dict[str, Any]:
    """
    Convert Emio BatchConfig (root_model + definitions) to canonical JSON Schema.
    config must have "root_model" (str) and "definitions" (list of model defs).
    Each definition: name, description?, fields: [{ name, type, required?, target_model? }].
    """
    root_model = config.get("root_model")
    if not root_model:
        raise ValueError("batch config must have root_model")
    definitions = config.get("definitions") or []
    if not definitions:
        raise ValueError("batch config must have at least one definition")

    defs_schema: dict[str, Any] = {}
    for model_def in definitions:
        name = model_def.get("name")
        if not name:
            raise ValueError("definition must have name")
        fields = model_def.get("fields") or []
        properties: dict[str, Any] = {}
        required: list[str] = []
        for f in fields:
            fname = f.get("name")
            if not fname:
                continue
            prop = _batch_field_type_to_json_schema(f)
            properties[fname] = prop
            if f.get("required", True):
                required.append(fname)
        defs_schema[name] = {
            "type": "object",
            "properties": properties,
            "required": required if required else [],
        }
        if model_def.get("description"):
            defs_schema[name]["description"] = model_def["description"]

    root_def = defs_schema.get(root_model)
    if not root_def:
        raise ValueError(f"root_model {root_model!r} not found in definitions")
    return {
        "$schema": _DRAFT_2020_12_META,
        "type": "object",
        "properties": root_def["properties"],
        "required": root_def.get("required", []),
        "$defs": defs_schema,
    }


def _json_schema_type_to_python(schema: dict[str, Any]) -> type:
    """Map JSON Schema type to Python type."""
    t = schema.get("type")
    if isinstance(t, list):
        t = t[0] if t else "string"
    if t == "string":
        return str
    if t == "integer":
        return int
    if t == "number":
        return float
    if t == "boolean":
        return bool
    if t == "array":
        return list
    if t == "object":
        return dict
    return str


def _build_model_from_json_schema(
    schema: dict[str, Any],
    class_name: str,
    defs: dict[str, Any],
    seen: set[str],
) -> Type[BaseModel]:
    """Recursively build a Pydantic model from JSON Schema (object with properties)."""
    if class_name in seen:
        raise ValueError(f"Circular $ref in schema: {class_name}")
    seen = seen | {class_name}
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    field_definitions: dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            field_definitions[prop_name] = (str, ...)
            continue
        if "$ref" in prop_schema:
            ref = prop_schema["$ref"]
            m = re.match(r"#/\$defs/(.+)$", ref)
            if m:
                ref_name = m.group(1)
                ref_schema = defs.get(ref_name)
                if ref_schema:
                    nested = _build_model_from_json_schema(
                        ref_schema, f"{class_name}_{ref_name}", defs, seen
                    )
                    field_definitions[prop_name] = (nested, ...)
                else:
                    field_definitions[prop_name] = (dict, ...)
            else:
                field_definitions[prop_name] = (dict, ...)
            continue
        if prop_schema.get("type") == "array":
            items = prop_schema.get("items")
            if isinstance(items, dict):
                if "$ref" in items:
                    m = re.match(r"#/\$defs/(.+)$", items["$ref"])
                    if m:
                        ref_name = m.group(1)
                        ref_schema = defs.get(ref_name)
                        if ref_schema:
                            nested = _build_model_from_json_schema(
                                ref_schema, f"{class_name}_{prop_name}Item", defs, seen
                            )
                            field_definitions[prop_name] = (list[nested], ...)
                        else:
                            field_definitions[prop_name] = (list[dict], ...)
                    else:
                        field_definitions[prop_name] = (list[dict], ...)
                else:
                    item_type = _json_schema_type_to_python(items)
                    field_definitions[prop_name] = (list[item_type], ...)
            else:
                field_definitions[prop_name] = (list[dict], ...)
            continue
        if prop_schema.get("type") == "object":
            nested_name = f"{class_name}_{prop_name.capitalize()}"
            nested = _build_model_from_json_schema(
                prop_schema, nested_name, defs, seen
            )
            field_definitions[prop_name] = (nested, ...)
            continue
        py_type = _json_schema_type_to_python(prop_schema)
        field_definitions[prop_name] = (py_type, ...) if prop_name in required else (py_type | None, None)
    return create_model(class_name, **field_definitions)


def simple_schema_to_canonical(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure schema is in canonical JSON Schema form. If it already has $schema or
    type+properties, return a copy with $schema set; otherwise treat as simple
    { field: type } and convert.
    """
    if not isinstance(schema, dict):
        raise TypeError("schema must be a dict")
    if schema.get("$schema") or (schema.get("type") == "object" and "properties" in schema):
        out = dict(schema)
        if not out.get("$schema"):
            out["$schema"] = _DRAFT_2020_12_META
        return out
    root = _simple_schema_to_json_schema(schema)
    root["$schema"] = _DRAFT_2020_12_META
    return root


def _simple_schema_to_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert simple { field_name: type_or_schema } to JSON Schema."""
    properties: dict[str, Any] = {}
    for key, val in schema.items():
        if key.startswith("$") or key in ("type", "properties", "required", "definitions", "$defs"):
            continue
        if isinstance(val, list):
            if val and isinstance(val[0], dict):
                properties[key] = {"type": "array", "items": _simple_schema_to_json_schema(val[0])}
            else:
                item_type = (val[0] if val else "string")
                type_map = {"string": "string", "number": "number", "integer": "integer", "boolean": "boolean"}
                properties[key] = {"type": "array", "items": {"type": type_map.get(str(item_type).lower(), "string")}}
        elif isinstance(val, dict) and ("type" in val or "properties" in val or "$ref" in val):
            properties[key] = val
        else:
            type_map = {"string": "string", "number": "number", "integer": "integer", "boolean": "boolean"}
            properties[key] = {"type": type_map.get(str(val).lower(), "string")}
    return {"type": "object", "properties": properties, "required": list(properties.keys())}


def canonical_schema_to_pydantic(
    schema: dict[str, Any],
    class_name: str = "DynamicModel",
) -> Type[BaseModel]:
    """
    Build a Pydantic model from canonical JSON Schema (type, properties, $defs, required),
    or from simple format { field_name: type_string | nested_schema }.
    """
    if not isinstance(schema, dict):
        raise TypeError("schema must be a dict")
    if schema.get("type") == "object" and "properties" in schema:
        defs = schema.get("$defs") or schema.get("definitions") or {}
        root = {"type": "object", "properties": schema["properties"], "required": schema.get("required", [])}
        return _build_model_from_json_schema(root, class_name, defs, set())
    # Simple format: keys are field names
    root = _simple_schema_to_json_schema(schema)
    return _build_model_from_json_schema(root, class_name, {}, set())
