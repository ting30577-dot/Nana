"""Fail-closed validation for Nana's small JSON-Schema subset."""

from __future__ import annotations

from typing import Any

from nana_sidecar.contracts.common import JsonObject


class SafeJsonSchemaError(ValueError):
    pass


_SUPPORTED_TYPES = frozenset(
    {"object", "array", "string", "integer", "number", "boolean", "null"}
)
_SUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "type",
        "required",
        "properties",
        "additionalProperties",
        "const",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "items",
        "minItems",
        "maxItems",
    }
)


def validate_safe_json_schema(schema: JsonObject, *, path: str = "$") -> None:
    """Validate the documented schema subset before it can enter policy state."""

    if not isinstance(schema, dict):
        raise SafeJsonSchemaError(f"{path}: schema must be an object")
    unknown = set(schema) - _SUPPORTED_SCHEMA_KEYS
    if unknown:
        raise SafeJsonSchemaError(
            f"{path}: unsupported schema keywords: {sorted(unknown)!r}"
        )

    expected_type = schema.get("type")
    if expected_type is not None and expected_type not in _SUPPORTED_TYPES:
        raise SafeJsonSchemaError(f"{path}: unsupported type")

    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise SafeJsonSchemaError(f"{path}.enum: must be a list")

    _validate_numeric_bounds(schema, "minimum", "maximum", path=path)
    _validate_integer_bounds(schema, "minLength", "maxLength", path=path)
    _validate_integer_bounds(schema, "minItems", "maxItems", path=path)

    if expected_type == "object":
        _validate_object_schema(schema, path=path)
    elif expected_type == "array":
        item_schema = schema.get("items", {})
        if not isinstance(item_schema, dict):
            raise SafeJsonSchemaError(f"{path}.items: must be an object")
        validate_safe_json_schema(item_schema, path=f"{path}.items")
    elif "properties" in schema or "required" in schema:
        raise SafeJsonSchemaError(
            f"{path}: properties and required require type=object"
        )
    elif "items" in schema:
        raise SafeJsonSchemaError(f"{path}: items requires type=array")


def safe_schema_matches(schema: JsonObject, value: Any) -> bool:
    """Return False for malformed schemas or mismatches; never leak TypeError."""

    try:
        validate_safe_json_schema(schema)
        return _matches(schema, value)
    except (SafeJsonSchemaError, TypeError, ValueError):
        return False


def _validate_object_schema(schema: JsonObject, *, path: str) -> None:
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    additional = schema.get("additionalProperties", False)
    if not isinstance(properties, dict):
        raise SafeJsonSchemaError(f"{path}.properties: must be an object")
    if not isinstance(required, list) or not all(
        isinstance(item, str) for item in required
    ):
        raise SafeJsonSchemaError(f"{path}.required: must be a string list")
    if len(set(required)) != len(required):
        raise SafeJsonSchemaError(f"{path}.required: duplicates are not allowed")
    if not set(required).issubset(properties):
        raise SafeJsonSchemaError(
            f"{path}.required: entries must be declared properties"
        )
    if additional not in (True, False):
        raise SafeJsonSchemaError(
            f"{path}.additionalProperties: must be boolean"
        )
    for name, child in properties.items():
        if not isinstance(name, str):
            raise SafeJsonSchemaError(f"{path}.properties: keys must be strings")
        if not isinstance(child, dict):
            raise SafeJsonSchemaError(
                f"{path}.properties.{name}: must be an object"
            )
        validate_safe_json_schema(child, path=f"{path}.properties.{name}")


def _validate_numeric_bounds(
    schema: JsonObject,
    minimum_key: str,
    maximum_key: str,
    *,
    path: str,
) -> None:
    minimum = schema.get(minimum_key)
    maximum = schema.get(maximum_key)
    for key, value in ((minimum_key, minimum), (maximum_key, maximum)):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            raise SafeJsonSchemaError(f"{path}.{key}: must be numeric")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise SafeJsonSchemaError(f"{path}: minimum exceeds maximum")


def _validate_integer_bounds(
    schema: JsonObject,
    minimum_key: str,
    maximum_key: str,
    *,
    path: str,
) -> None:
    minimum = schema.get(minimum_key)
    maximum = schema.get(maximum_key)
    for key, value in ((minimum_key, minimum), (maximum_key, maximum)):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise SafeJsonSchemaError(f"{path}.{key}: must be a non-negative int")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise SafeJsonSchemaError(f"{path}: minimum exceeds maximum")


def _matches(schema: JsonObject, value: Any) -> bool:
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            return False
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not set(required).issubset(value):
            return False
        if not schema.get("additionalProperties", False) and not set(
            value
        ).issubset(properties):
            return False
        return all(
            key not in value or _matches(child_schema, value[key])
            for key, child_schema in properties.items()
        )
    if expected_type == "array":
        return (
            isinstance(value, list)
            and _length_matches(schema, value, "minItems", "maxItems")
            and all(_matches(schema.get("items", {}), item) for item in value)
        )
    if expected_type == "string":
        return isinstance(value, str) and _length_matches(
            schema,
            value,
            "minLength",
            "maxLength",
        )
    if expected_type == "integer":
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and _number_matches(schema, value)
        )
    if expected_type == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and _number_matches(schema, value)
        )
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return expected_type is None


def _length_matches(
    schema: JsonObject,
    value: Any,
    minimum_key: str,
    maximum_key: str,
) -> bool:
    minimum = schema.get(minimum_key)
    maximum = schema.get(maximum_key)
    return (
        (minimum is None or len(value) >= minimum)
        and (maximum is None or len(value) <= maximum)
    )


def _number_matches(schema: JsonObject, value: int | float) -> bool:
    minimum = schema.get("minimum")
    maximum = schema.get("maximum")
    return (
        (minimum is None or value >= minimum)
        and (maximum is None or value <= maximum)
    )
