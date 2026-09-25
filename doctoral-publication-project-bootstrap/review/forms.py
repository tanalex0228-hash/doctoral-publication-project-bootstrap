from django import forms
from publications.models import PublicationRecord


class ReturnForRevisionForm(forms.Form):
    reason = forms.CharField(label="退回原因（選填）", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}))


class PublicationSettingsForm(forms.Form):
    is_published = forms.BooleanField(label="在平台發佈", required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    visibility_scope = forms.ChoiceField(label="可見範圍", choices=PublicationRecord.VisibilityScope.choices, widget=forms.Select(attrs={"class": "form-select"}))
