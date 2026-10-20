from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.models import Category
from catalog.validators import MetadataSchemaError, validate_metadata, validate_metadata_schema

FUNKO_SCHEMA = [
    {
        "key": "box_condition",
        "label": "Box condition (1\u201310)",
        "type": "int",
        "required": True,
        "min": 1,
        "max": 10,
    },
    {
        "key": "original_box_included",
        "label": "Original box included",
        "type": "bool",
        "required": True,
    },
    {
        "key": "serial_number",
        "label": "Serial number",
        "type": "str",
        "required": True,
    },
]

LEGO_SCHEMA = [
    {
        "key": "sealed_misb",
        "label": "Factory sealed (MISB)",
        "type": "bool",
        "required": True,
    },
    {
        "key": "missing_parts",
        "label": "Missing parts",
        "type": "bool",
        "required": True,
    },
    {
        "key": "year",
        "label": "Year",
        "type": "int",
        "required": True,
    },
]

TCG_SCHEMA = [
    {
        "key": "grading",
        "label": "Grading (company and score)",
        "type": "str",
        "required": False,
    },
    {
        "key": "card_condition",
        "label": "Card condition",
        "type": "str",
        "required": True,
        "choices": ["Mint", "Near Mint", "Played"],
    },
]

SCHEMAS = {
    "funko": FUNKO_SCHEMA,
    "lego": LEGO_SCHEMA,
    "tcg": TCG_SCHEMA,
}

FUNKO_VALID = {
    "box_condition": 7,
    "original_box_included": True,
    "serial_number": "FP-0001",
}
LEGO_VALID = {
    "sealed_misb": False,
    "missing_parts": False,
    "year": 2019,
}
TCG_VALID = {"card_condition": "Near Mint"}


class MetadataValidatorTests(TestCase):
    def setUp(self):
        self.categories = {
            slug: Category.objects.create(
                slug=slug,
                name=slug,
                metadata_schema=schema,
            )
            for slug, schema in SCHEMAS.items()
        }

    def _assert_message(self, category, metadata, key, message):
        with self.assertRaises(ValidationError) as raised:
            validate_metadata(category, metadata)
        self.assertEqual(raised.exception.message_dict[key], [message])

    def test_valid_funko_metadata_passes(self):
        """Spec 03 case 1: valid funko metadata passes."""
        validate_metadata(self.categories["funko"], dict(FUNKO_VALID))

    def test_valid_lego_metadata_passes(self):
        """Spec 03 case 1: valid lego metadata passes."""
        validate_metadata(self.categories["lego"], dict(LEGO_VALID))

    def test_valid_tcg_metadata_without_grading_passes(self):
        """Spec 03 case 1: tcg metadata without grading passes."""
        validate_metadata(self.categories["tcg"], dict(TCG_VALID))

    def test_valid_tcg_metadata_with_grading_passes(self):
        """Spec 03 case 1: tcg metadata with grading passes."""
        validate_metadata(
            self.categories["tcg"],
            {"grading": "PSA 10", "card_condition": "Mint"},
        )

    def test_missing_required_keys_are_rejected(self):
        """Spec 03 case 2: dropping a required key reports Missing required field."""
        required = {
            "funko": ("box_condition", "original_box_included", "serial_number"),
            "lego": ("sealed_misb", "missing_parts", "year"),
            "tcg": ("card_condition",),
        }
        bases = {
            "funko": FUNKO_VALID,
            "lego": LEGO_VALID,
            "tcg": TCG_VALID,
        }
        for slug, keys in required.items():
            for key in keys:
                metadata = dict(bases[slug])
                metadata.pop(key)
                with self.subTest(slug=slug, key=key):
                    self._assert_message(
                        self.categories[slug],
                        metadata,
                        key,
                        f'Missing required field "{key}".',
                    )

    def test_missing_optional_grading_is_accepted(self):
        """Spec 03 case 2: dropping optional tcg grading is accepted."""
        validate_metadata(self.categories["tcg"], {"card_condition": "Mint"})

    def test_blank_required_serial_number_is_rejected(self):
        """Spec 03 case 3: a blank required string is rejected."""
        for blank in ("", "   "):
            metadata = dict(FUNKO_VALID)
            metadata["serial_number"] = blank
            with self.subTest(blank=blank):
                with self.assertRaises(ValidationError):
                    validate_metadata(self.categories["funko"], metadata)

    def test_blank_optional_grading_is_accepted(self):
        """Spec 03 case 3: a blank optional grading string is accepted."""
        validate_metadata(
            self.categories["tcg"],
            {"grading": "", "card_condition": "Mint"},
        )

    def test_box_condition_out_of_range_is_rejected(self):
        """Spec 03 case 4: box_condition 0 and 11 are rejected with the range message."""
        for value in (0, 11):
            metadata = dict(FUNKO_VALID)
            metadata["box_condition"] = value
            with self.subTest(value=value):
                self._assert_message(
                    self.categories["funko"],
                    metadata,
                    "box_condition",
                    '"box_condition" must be between 1 and 10.',
                )

    def test_box_condition_bounds_are_accepted(self):
        """Spec 03 case 4: box_condition 1 and 10 are accepted."""
        for value in (1, 10):
            metadata = dict(FUNKO_VALID)
            metadata["box_condition"] = value
            with self.subTest(value=value):
                validate_metadata(self.categories["funko"], metadata)

    def test_box_condition_non_integers_are_rejected(self):
        """Spec 03 case 5: string, float, and boolean box_condition values are rejected."""
        for value in ("7", 7.5, True):
            metadata = dict(FUNKO_VALID)
            metadata["box_condition"] = value
            with self.subTest(value=value):
                self._assert_message(
                    self.categories["funko"],
                    metadata,
                    "box_condition",
                    '"box_condition" must be a whole number.',
                )

    def test_card_condition_outside_choices_is_rejected(self):
        """Spec 03 case 6: card_condition values outside the choices are rejected."""
        for value in ("Good", "mint"):
            with self.subTest(value=value):
                self._assert_message(
                    self.categories["tcg"],
                    {"card_condition": value},
                    "card_condition",
                    '"card_condition" must be one of: Mint, Near Mint, Played.',
                )

    def test_card_condition_choices_are_accepted(self):
        """Spec 03 case 6: each allowed card_condition value is accepted."""
        for value in ("Mint", "Near Mint", "Played"):
            with self.subTest(value=value):
                validate_metadata(self.categories["tcg"], {"card_condition": value})

    def test_wrong_metadata_types_are_rejected(self):
        """Spec 03 case 7: a value of the wrong type gets that type's message."""
        cases = (
            (
                "lego",
                {**LEGO_VALID, "year": "2019"},
                "year",
                '"year" must be a whole number.',
            ),
            (
                "lego",
                {**LEGO_VALID, "sealed_misb": "yes"},
                "sealed_misb",
                '"sealed_misb" must be yes or no.',
            ),
            (
                "funko",
                {**FUNKO_VALID, "serial_number": 123},
                "serial_number",
                '"serial_number" must be text.',
            ),
        )
        for slug, metadata, key, message in cases:
            with self.subTest(key=key):
                self._assert_message(self.categories[slug], metadata, key, message)

    def test_undeclared_key_is_rejected(self):
        """Spec 03 case 8: an undeclared character key is rejected."""
        metadata = dict(FUNKO_VALID)
        metadata["character"] = "Batman"
        self._assert_message(
            self.categories["funko"],
            metadata,
            "__all__",
            'Unknown metadata field "character".',
        )

    def test_non_object_metadata_is_rejected(self):
        """Spec 03 case 9: a list, a string, and None are not metadata objects."""
        for value in ([], "x", None):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as raised:
                    validate_metadata(self.categories["funko"], value)
                self.assertEqual(
                    raised.exception.messages,
                    ["Metadata must be an object."],
                )

    def test_required_false_booleans_are_valid(self):
        """Spec 03 case 10: a required bool set to false is a present valid value."""
        funko = dict(FUNKO_VALID)
        funko["original_box_included"] = False
        validate_metadata(self.categories["funko"], funko)
        validate_metadata(self.categories["lego"], dict(LEGO_VALID))

    def test_generic_schema_enforces_bounds_choices_and_optional_absence(self):
        """Spec 03 case 11: a test category's min, max, and choices are enforced with no code change."""
        category = Category.objects.create(
            slug="test",
            name="Test",
            metadata_schema=[
                {
                    "key": "count",
                    "label": "Count",
                    "type": "int",
                    "required": True,
                    "min": 0,
                    "max": 5,
                },
                {
                    "key": "kind",
                    "label": "Kind",
                    "type": "str",
                    "required": True,
                    "choices": ["a", "b"],
                },
                {
                    "key": "note",
                    "label": "Note",
                    "type": "str",
                    "required": False,
                },
            ],
        )
        validate_metadata(category, {"count": 0, "kind": "a"})
        validate_metadata(category, {"count": 5, "kind": "b", "note": "hello"})

        self._assert_message(
            category,
            {"count": -1, "kind": "a"},
            "count",
            '"count" must be between 0 and 5.',
        )
        self._assert_message(
            category,
            {"count": 6, "kind": "a"},
            "count",
            '"count" must be between 0 and 5.',
        )
        self._assert_message(
            category,
            {"count": 1, "kind": "c"},
            "kind",
            '"kind" must be one of: a, b.',
        )

    def _assert_schema_error(self, schema, entry_key, offending_key):
        with self.assertRaises(MetadataSchemaError) as raised:
            validate_metadata_schema(schema, slug="test")
        error = raised.exception
        self.assertEqual(error.slug, "test")
        self.assertEqual(error.entry_key, entry_key)
        self.assertEqual(error.offending_key, offending_key)

    def test_schema_rejects_min_on_a_str_entry(self):
        """Spec 03 case 12: min on a str entry is a configuration error."""
        self._assert_schema_error(
            [
                {
                    "key": "note",
                    "label": "Note",
                    "type": "str",
                    "required": True,
                    "min": 1,
                }
            ],
            "note",
            "min",
        )

    def test_schema_rejects_choices_on_an_int_entry(self):
        """Spec 03 case 12: choices on an int entry is a configuration error."""
        self._assert_schema_error(
            [
                {
                    "key": "count",
                    "label": "Count",
                    "type": "int",
                    "required": True,
                    "choices": ["a"],
                }
            ],
            "count",
            "choices",
        )

    def test_schema_rejects_min_greater_than_max(self):
        """Spec 03 case 12: min greater than max is a configuration error."""
        with self.assertRaises(MetadataSchemaError) as raised:
            validate_metadata_schema(
                [
                    {
                        "key": "count",
                        "label": "Count",
                        "type": "int",
                        "required": True,
                        "min": 5,
                        "max": 1,
                    }
                ],
                slug="test",
            )
        error = raised.exception
        self.assertEqual(error.slug, "test")
        self.assertEqual(error.entry_key, "count")
        self.assertIn(error.offending_key, {"min", "max"})

    def test_schema_rejects_empty_choices(self):
        """Spec 03 case 12: an empty choices list is a configuration error."""
        self._assert_schema_error(
            [
                {
                    "key": "kind",
                    "label": "Kind",
                    "type": "str",
                    "required": True,
                    "choices": [],
                }
            ],
            "kind",
            "choices",
        )

    def test_schema_rejects_unknown_type(self):
        """Spec 03 case 12: an unknown type is a configuration error."""
        self._assert_schema_error(
            [
                {
                    "key": "note",
                    "label": "Note",
                    "type": "float",
                    "required": True,
                }
            ],
            "note",
            "type",
        )

    def test_schema_rejects_missing_label(self):
        """Spec 03 case 12: a missing label is a configuration error."""
        self._assert_schema_error(
            [{"key": "note", "type": "str", "required": True}],
            "note",
            "label",
        )

    def test_schema_rejects_unknown_entry_key(self):
        """Spec 03 case 12: an unknown entry key named default is a configuration error."""
        self._assert_schema_error(
            [
                {
                    "key": "note",
                    "label": "Note",
                    "type": "str",
                    "required": True,
                    "default": "x",
                }
            ],
            "note",
            "default",
        )

    def test_schema_rejects_duplicate_key(self):
        """Spec 03 case 12: two entries with the same key are a configuration error."""
        self._assert_schema_error(
            [
                {"key": "note", "label": "Note", "type": "str", "required": True},
                {"key": "note", "label": "Again", "type": "str", "required": False},
            ],
            "note",
            "key",
        )

    def test_mvp_schemas_pass_configuration_check(self):
        """Spec 03 case 12: the three MVP schemas pass validate_metadata_schema."""
        for slug, schema in SCHEMAS.items():
            with self.subTest(slug=slug):
                validate_metadata_schema(schema, slug=slug)
