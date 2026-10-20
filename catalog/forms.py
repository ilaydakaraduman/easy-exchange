from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from .validators import validate_metadata, validate_metadata_schema


class ListingPhotoField(forms.ImageField):
    default_error_messages = {
        "invalid_image": "Upload a JPEG, PNG, or WebP image.",
    }

    def to_python(self, data):
        if data in self.empty_values:
            return None
        if getattr(data, "size", 0) > 5 * 1024 * 1024:
            raise ValidationError(
                "Image must be 5 MB or smaller.",
                code="max_size",
            )
        return super().to_python(data)


class ListingForm(forms.Form):
    title = forms.CharField(label="Title", max_length=120)
    description = forms.CharField(
        label="Description",
        widget=forms.Textarea,
    )
    photo = ListingPhotoField(
        label="Photo",
        required=False,
        widget=forms.FileInput(
            attrs={"accept": "image/jpeg,image/png,image/webp"},
        ),
    )

    def __init__(self, *args, category, **kwargs):
        self.category = category
        self.cleaned_metadata = {}
        validate_metadata_schema(
            category.metadata_schema,
            slug=getattr(category, "slug", None),
        )
        super().__init__(*args, **kwargs)
        for entry in category.metadata_schema:
            self.fields[entry["key"]] = _field_for_entry(entry)

    def clean(self):
        cleaned_data = super().clean()
        metadata = {}
        for entry in self.category.metadata_schema:
            key = entry["key"]
            if key in self.errors or key not in cleaned_data:
                continue
            value = cleaned_data[key]
            if entry["type"] == "str":
                if not entry["required"] and value == "":
                    continue
            elif value is None:
                continue
            metadata[key] = value
        self.cleaned_metadata = metadata
        try:
            validate_metadata(self.category, metadata)
        except ValidationError as exc:
            _apply_metadata_errors(self, exc)
        return cleaned_data

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo
        from io import BytesIO

        from PIL import Image

        raw = photo.read()
        if hasattr(photo, "seek"):
            photo.seek(0)
        try:
            with Image.open(BytesIO(raw)) as image:
                image_format = image.format
        except Exception as exc:
            raise ValidationError("Upload a JPEG, PNG, or WebP image.") from exc
        if image_format not in {"JPEG", "PNG", "WEBP"}:
            raise ValidationError("Upload a JPEG, PNG, or WebP image.")
        return photo


def initial_from_item(item):
    initial = {
        "title": item.title,
        "description": item.description,
    }
    metadata = item.metadata or {}
    for entry in item.category.metadata_schema:
        key = entry["key"]
        if key in metadata:
            initial[key] = metadata[key]
    return initial


def _field_for_entry(entry):
    label = entry["label"]
    required = bool(entry["required"])
    if entry["type"] == "int":
        kwargs = {"label": label, "required": required}
        if "min" in entry:
            kwargs["min_value"] = entry["min"]
        if "max" in entry:
            kwargs["max_value"] = entry["max"]
        if "min" in entry and "max" in entry:
            message = (
                f"Ensure this value is between {entry['min']} and {entry['max']}."
            )
            kwargs["error_messages"] = {
                "min_value": message,
                "max_value": message,
            }
        return forms.IntegerField(**kwargs)
    if entry["type"] == "bool":
        return forms.BooleanField(label=label, required=False)
    if "choices" in entry:
        choices = [("", "")] + [(choice, choice) for choice in entry["choices"]]
        return forms.ChoiceField(label=label, required=required, choices=choices)
    return forms.CharField(label=label, required=required)


def _apply_metadata_errors(form, exc):
    if hasattr(exc, "error_dict"):
        for field, errors in exc.error_dict.items():
            if field != NON_FIELD_ERRORS and field in form.errors:
                continue
            target = None if field == NON_FIELD_ERRORS else field
            for error in errors:
                form.add_error(target, error)
        return
    form.add_error(None, exc)
