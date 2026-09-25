from django import forms
from publications.models import PublicationRecord


class ReturnForRevisionForm(forms.Form):
    reason = forms.CharField(label="退回原因（選填）", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}))


class RevokeApprovalForm(forms.Form):
    reason = forms.CharField(label="撤銷原因", required=True, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    confirm = forms.BooleanField(
        label="我確認撤銷目前核准，成果將不再列入正式統計與對外可見範圍。",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class PublicationSettingsForm(forms.Form):
    is_published = forms.BooleanField(label="在平台發佈", required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    visibility_scope = forms.ChoiceField(label="可見範圍", choices=PublicationRecord.VisibilityScope.choices, widget=forms.Select(attrs={"class": "form-select"}))
