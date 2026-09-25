import re

from django import forms
from django.core.exceptions import ValidationError
from .models import PublicationAuthor, PublicationRecord
from taxonomy.models import PublicationIndex, PublicationType, ResearchField


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs["class"] = "form-control"


class PublicationForm(BootstrapFormMixin, forms.ModelForm):
    indices = forms.ModelMultipleChoiceField(queryset=PublicationIndex.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)
    research_fields = forms.ModelMultipleChoiceField(queryset=ResearchField.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = PublicationRecord
        fields = ["publication_type", "title", "abstract", "journal_or_conference_name", "language", "doi", "issn", "volume", "issue", "pages_or_article_number", "publication_stage", "submitted_to_journal_date", "accepted_date", "publication_date"]
        widgets = {"abstract": forms.Textarea(attrs={"rows": 5}), "submitted_to_journal_date": forms.DateInput(attrs={"type": "date"}), "accepted_date": forms.DateInput(attrs={"type": "date"}), "publication_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publication_type"].queryset = PublicationType.objects.filter(is_active=True)
        self.fields["indices"].queryset = PublicationIndex.objects.filter(is_active=True)
        self.fields["research_fields"].queryset = ResearchField.objects.filter(is_active=True)
        if self.instance and self.instance.pk:
            self.initial["indices"] = self.instance.indices.all()
            self.initial["research_fields"] = self.instance.research_fields.all()

    def clean_issn(self):
        """Accept a conventional ISSN only when its ISO 3297 check digit is valid."""
        value = (self.cleaned_data.get("issn") or "").strip().upper().replace(" ", "")
        if not value:
            return None
        compact = value.replace("-", "")
        if not re.fullmatch(r"\d{7}[\dX]", compact):
            raise ValidationError("ISSN 格式應為 1234-567X。")
        expected = (11 - sum(int(digit) * weight for digit, weight in zip(compact[:7], range(8, 1, -1))) % 11) % 11
        check_digit = 10 if compact[-1] == "X" else int(compact[-1])
        if check_digit != expected:
            raise ValidationError("ISSN 檢查碼無效。")
        return f"{compact[:4]}-{compact[4:]}"


class PublicationAuthorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PublicationAuthor
        fields = ["display_name", "affiliation", "is_corresponding_author", "linked_user", "linked_professor", "orcid"]


def publication_form_values(form):
    values = {field: form.cleaned_data[field] for field in PublicationForm.Meta.fields}
    return values, form.cleaned_data["indices"], form.cleaned_data["research_fields"]


def author_form_values(form):
    return {field: form.cleaned_data[field] for field in PublicationAuthorForm.Meta.fields}
