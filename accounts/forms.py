from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

User = get_user_model()


class RegistrationForm(forms.Form):
    display_name = forms.CharField(
        label="Display name",
        min_length=2,
        max_length=40,
    )
    email = forms.EmailField(label="Email")
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
    )
    confirm_password = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput,
    )

    def clean_display_name(self):
        return self.cleaned_data["display_name"].strip()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        if password:
            user = User(
                email=cleaned_data.get("email", ""),
                display_name=cleaned_data.get("display_name", ""),
            )
            try:
                password_validation.validate_password(password, user)
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned_data


class LoginForm(forms.Form):
    email = forms.CharField(label="Email")
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

