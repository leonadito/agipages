from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    """Kept only because accounts/migrations/0001_initial.py references
    `accounts.models.UserManager` in its historical model state (from when
    this model was email-only, USERNAME_FIELD='email') — that migration is
    already applied on deployed databases and must not be rewritten, so
    Django needs this class importable even though it's no longer assigned
    to `User.objects` (see `User` below, which now uses AbstractUser's
    default username-based manager). Do not delete unless 0001_initial is
    squashed."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Standard Django username-based auth (USERNAME_FIELD/REQUIRED_FIELDS
    inherited as-is from AbstractUser — only `email` is tightened to unique
    and `tenant` is added). Tenant is nullable so a platform superuser can
    exist without belonging to any tenant. Uses AbstractUser's own default
    manager (username-based `create_user`/`create_superuser`), not the
    `UserManager` above — that one is email-only and kept solely for
    migration-history compatibility (see its docstring)."""

    email = models.EmailField("endereço de e-mail", unique=True)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
    )

    def __str__(self):
        return self.username
