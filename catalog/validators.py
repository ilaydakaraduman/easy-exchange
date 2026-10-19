from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

ALLOWED_ENTRY_KEYS = {"key", "label", "type", "required", "min", "max", "choices"}
ALLOWED_TYPES = {"int", "bool", "str"}
REQUIRED_ENTRY_KEYS = ("key", "label", "type", "required")


class MetadataSchemaError(Exception):
    """A category metadata_schema is misconfigured.

    Names the category slug (when the caller knows it), the entry key, and
    the offending entry key. This is a developer error, not a form error.
    """

    def __init__(self, slug, entry_key, offending_key):
        self.slug = slug
        self.entry_key = entry_key
        self.offending_key = offending_key
        slug_text = slug if slug else "unknown"
        entry_text = entry_key if entry_key else "unknown"
        super().__init__(
            f'Category "{slug_text}" entry "{entry_text}" '
            f'has invalid "{offending_key}".'
        )


def validate_metadata_schema(schema, slug=None):
    if not isinstance(schema, list):
        raise MetadataSchemaError(slug, None, "metadata_schema")

    seen_keys = set()
    for entry in schema:
        if not isinstance(entry, dict):
            raise MetadataSchemaError(slug, None, "entry")

        entry_key = entry.get("key")
        for required_key in REQUIRED_ENTRY_KEYS:
            if required_key not in entry or entry[required_key] is None:
                raise MetadataSchemaError(slug, _entry_name(entry_key), required_key)

        for present_key in entry:
            if present_key not in ALLOWED_ENTRY_KEYS:
                raise MetadataSchemaError(slug, _entry_name(entry_key), present_key)

        if not isinstance(entry_key, str) or entry_key == "":
            raise MetadataSchemaError(slug, None, "key")

        entry_type = entry["type"]
        if entry_type not in ALLOWED_TYPES:
            raise MetadataSchemaError(slug, entry_key, "type")

        if "min" in entry or "max" in entry:
            _check_bounds(slug, entry_key, entry_type, entry)

        if "choices" in entry:
            if entry_type != "str" or not _valid_choices(entry["choices"]):
                raise MetadataSchemaError(slug, entry_key, "choices")

        if entry_key in seen_keys:
            raise MetadataSchemaError(slug, entry_key, "key")
        seen_keys.add(entry_key)


def validate_metadata(category, metadata):
    validate_metadata_schema(
        category.metadata_schema,
        slug=getattr(category, "slug", None),
    )
    if not isinstance(metadata, dict):
        raise ValidationError("Metadata must be an object.")

    errors = {}
    declared = {}
    for entry in category.metadata_schema:
        key = entry["key"]
        declared[key] = entry
        if entry["required"] and _required_missing(entry, metadata):
            _add(errors, key, f'Missing required field "{key}".')
            continue
        if key not in metadata:
            continue
        value = metadata[key]
        type_message = _type_message(key, entry, value)
        if type_message:
            _add(errors, key, type_message)
            continue
        rule_message = _rule_message(key, entry, value)
        if rule_message:
            _add(errors, key, rule_message)

    for key in metadata:
        if key not in declared:
            _add(errors, NON_FIELD_ERRORS, f'Unknown metadata field "{key}".')

    if errors:
        raise ValidationError(errors)


def _entry_name(entry_key):
    if isinstance(entry_key, str) and entry_key:
        return entry_key
    return None


def _is_whole_number(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_bounds(slug, entry_key, entry_type, entry):
    if entry_type != "int":
        offending = "min" if "min" in entry else "max"
        raise MetadataSchemaError(slug, entry_key, offending)
    if "min" in entry and not _is_whole_number(entry["min"]):
        raise MetadataSchemaError(slug, entry_key, "min")
    if "max" in entry and not _is_whole_number(entry["max"]):
        raise MetadataSchemaError(slug, entry_key, "max")
    if (
        "min" in entry
        and "max" in entry
        and entry["min"] > entry["max"]
    ):
        raise MetadataSchemaError(slug, entry_key, "min")


def _valid_choices(choices):
    if not isinstance(choices, list) or not choices:
        return False
    if not all(isinstance(choice, str) for choice in choices):
        return False
    return len(set(choices)) == len(choices)


def _required_missing(entry, metadata):
    key = entry["key"]
    if key not in metadata:
        return True
    value = metadata[key]
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _type_message(key, entry, value):
    entry_type = entry["type"]
    if entry_type == "int" and not _is_whole_number(value):
        return f'"{key}" must be a whole number.'
    if entry_type == "bool" and not isinstance(value, bool):
        return f'"{key}" must be yes or no.'
    if entry_type == "str" and not isinstance(value, str):
        return f'"{key}" must be text.'
    return None


def _rule_message(key, entry, value):
    if entry["type"] == "int" and ("min" in entry or "max" in entry):
        lower = entry.get("min")
        upper = entry.get("max")
        below = lower is not None and value < lower
        above = upper is not None and value > upper
        if below or above:
            if lower is not None and upper is not None:
                return f'"{key}" must be between {lower} and {upper}.'
            if lower is not None:
                return f'"{key}" must be greater than or equal to {lower}.'
            return f'"{key}" must be less than or equal to {upper}.'
    if entry["type"] == "str" and "choices" in entry:
        if value not in entry["choices"]:
            listed = ", ".join(entry["choices"])
            return f'"{key}" must be one of: {listed}.'
    return None


def _add(errors, field, message):
    errors.setdefault(field, []).append(message)
