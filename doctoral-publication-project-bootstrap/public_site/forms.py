from django import forms

from taxonomy.models import PublicationIndex, PublicationType, ResearchField


class PortalFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=255, label="關鍵字")
    year = forms.IntegerField(required=False, min_value=1, label="發表年度")
    publication_type = forms.ModelChoiceField(queryset=PublicationType.objects.none(), required=False, label="成果類型")
    publication_index = forms.ModelChoiceField(queryset=PublicationIndex.objects.none(), required=False, label="Publication Index")
    research_field = forms.ModelChoiceField(queryset=ResearchField.objects.none(), required=False, label="研究領域")
    language = forms.CharField(required=False, max_length=16, label="語言")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publication_type"].queryset = PublicationType.objects.filter(is_active=True)
        self.fields["publication_index"].queryset = PublicationIndex.objects.filter(is_active=True)
        self.fields["research_field"].queryset = ResearchField.objects.filter(is_active=True)
        self.fields["q"].widget.attrs["placeholder"] = "標題、作者、期刊／會議、DOI"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
