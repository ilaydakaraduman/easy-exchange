"""MVP category metadata schemas.

Seed and tests share these literals. The validator and listing form stay
generic: they read whatever schema is stored on the Category row.
"""

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

MVP_CATEGORIES = (
    {
        "slug": "funko",
        "name": "Funko Pop & Figures",
        "metadata_schema": FUNKO_SCHEMA,
    },
    {
        "slug": "lego",
        "name": "Lego Sets & Minifigures",
        "metadata_schema": LEGO_SCHEMA,
    },
    {
        "slug": "tcg",
        "name": "Trading Card Games",
        "metadata_schema": TCG_SCHEMA,
    },
)
