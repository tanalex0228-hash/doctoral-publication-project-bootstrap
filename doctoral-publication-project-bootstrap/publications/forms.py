from django import forms
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


class PublicationAuthorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PublicationAuthor
        fields = ["display_name", "affiliation", "is_corresponding_author", "linked_user", "linked_professor", "orcid"]


def publication_form_values(form):
    values = {field: form.cleaned_data[field] for field in PublicationForm.Meta.fields}
    return values, form.cleaned_data["indices"], form.cleaned_data["research_fields"]


def author_form_values(form):
    return {field: form.cleaned_data[field] for field in PublicationAuthorForm.Meta.fields}
