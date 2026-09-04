from django import forms


class LeadCaptureForm(forms.Form):
    """Campos sempre presentes: nome + honeypot. E-mail, telefone, cidade e
    quaisquer campos extras são adicionados dinamicamente por
    build_lead_capture_form, de acordo com a LandingPage — por isso este é
    um forms.Form simples, não um ModelForm (o conjunto de campos varia por
    instância, então um Meta.fields fixo não serve mais)."""

    name = forms.CharField(label="Nome", max_length=255)

    # Honeypot: a real visitor never sees or fills this field (hidden via
    # CSS in the template); bots that auto-fill every input do. Any value
    # here means spam — reject silently, don't create a Lead.
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Envio inválido.")
        return value


def _build_field_for(form_field):
    """Traduz um LandingPageFormField em um campo de forms.Form."""
    common = {"label": form_field.label, "required": form_field.required}
    if form_field.field_type == form_field.EMAIL:
        return forms.EmailField(**common)
    if form_field.field_type == form_field.TEXTAREA:
        return forms.CharField(widget=forms.Textarea, **common)
    if form_field.field_type == form_field.SELECT:
        choices = [(opt, opt) for opt in form_field.options()]
        return forms.ChoiceField(choices=choices, widget=forms.Select, **common)
    if form_field.field_type == form_field.RADIO:
        choices = [(opt, opt) for opt in form_field.options()]
        return forms.ChoiceField(choices=choices, widget=forms.RadioSelect, **common)
    if form_field.field_type == form_field.CHECKBOX:
        return forms.BooleanField(**common)
    # TEXT, PHONE (e qualquer valor desconhecido) caem em texto simples.
    return forms.CharField(**common)


def extra_field_name(field_key):
    return f"extra_{field_key}"


def build_lead_capture_form(landing_page, data=None):
    """Monta o LeadCaptureForm dinamicamente para uma LandingPage: adiciona
    e-mail/telefone só se habilitados (com a obrigatoriedade configurada),
    sempre adiciona cidade, e adiciona um campo por LandingPageFormField
    configurado na página, na ordem definida."""
    form = LeadCaptureForm(data)

    if landing_page.show_email:
        form.fields["email"] = forms.EmailField(
            label="Email", required=landing_page.require_email
        )
    if landing_page.show_phone:
        form.fields["phone"] = forms.CharField(
            label=landing_page.phone_label or "Telefone",
            max_length=30,
            required=landing_page.require_phone,
        )
    form.fields["city"] = forms.CharField(label="Cidade", max_length=100, required=True)

    for form_field in landing_page.form_fields.all():
        form.fields[extra_field_name(form_field.field_key)] = _build_field_for(form_field)

    return form


def extract_extra_field_values(landing_page, cleaned_data):
    return {
        form_field.field_key: cleaned_data.get(extra_field_name(form_field.field_key))
        for form_field in landing_page.form_fields.all()
    }
