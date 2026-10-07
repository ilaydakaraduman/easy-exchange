from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinLengthValidator
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        return (email or "").strip().lower()

    def create_user(self, email, display_name, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        display_name = (display_name or "").strip()
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=email, display_name=display_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, display_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, display_name, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(
        max_length=40,
        validators=[MinLengthValidator(2)],
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    objects = UserManager()

    def __str__(self):
        return self.email
