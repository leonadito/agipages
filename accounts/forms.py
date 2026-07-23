from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import transaction
from django.utils.text import slugify

from tenants.models import Tenant

from .models import User


class SignupForm(forms.Form):
    tenant_name = forms.CharField(label="Nome da imobiliária/conta", max_length=255)
    username = forms.CharField(
        label="Usuário", max_length=150, validators=[UnicodeUsernameValidator()]
    )
    email = forms.EmailField(label="E-mail")
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirme a senha", widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nome de usuário já está em uso.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("As senhas não coincidem.")
        if password2:
            password_validation.validate_password(password2)
        return password2

    def _unique_tenant_slug(self, name):
        base_slug = slugify(name)[:90] or "tenant"
        slug = base_slug
        suffix = 1
        while Tenant.objects.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base_slug}-{suffix}"
        return slug

    @transaction.atomic
    def save(self):
        tenant = Tenant.objects.create(
            name=self.cleaned_data["tenant_name"],
            slug=self._unique_tenant_slug(self.cleaned_data["tenant_name"]),
        )
        return User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password2"],
            tenant=tenant,
        )
