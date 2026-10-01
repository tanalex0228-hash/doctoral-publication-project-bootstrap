import re

from django import forms
from django.core.exceptions import ValidationError
from .models import (
    ConferenceDetail, ConferencePresentationMode, Country, JournalArticleDetail,
    PublicationAuthor, PublicationRecord, SustainableDevelopmentGoal,
)
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


class JournalArticleDetailForm(BootstrapFormMixin, forms.ModelForm):
    sdgs = forms.ModelMultipleChoiceField(
        queryset=SustainableDevelopmentGoal.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = JournalArticleDetail
        exclude = ["id", "publication", "legacy_journal_type"]
        labels = {
            "journal_type": "期刊類型", "international_journal_rank": "SCI／SSCI 期刊排名",
            "impact_factor": "Impact factor", "taiwan_journal_level": "臺灣期刊收錄級別",
            "custom_journal_type": "期刊類型說明", "student_author_order": "學生作者序",
            "student_author_order_reason": "第四作者（含）以後原因", "student_author_attribute": "學生作者屬性",
            "is_student_corresponding_author": "學生是否為通訊作者", "has_international_collaboration": "是否國際合作",
            "publication_medium": "出版媒體", "paper_nature": "論文性質", "paper_attribute": "論文屬性",
            "total_pages": "總頁數", "is_annual_representative_work": "年度代表作", "is_peer_reviewed": "是否具審查機制",
            "citation_count": "引用次數", "publication_country": "出版國", "publication_place": "出版地", "remarks": "備註",
        }
        widgets = {"remarks": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publication_country"].queryset = Country.objects.filter(is_active=True)
        self.fields["sdgs"].queryset = SustainableDevelopmentGoal.objects.filter(is_active=True)
        if self.instance and not self.instance._state.adding:
            self.initial["sdgs"] = self.instance.publication.sdg_assignments.values_list("goal", flat=True)

    def clean_sdgs(self):
        goals = self.cleaned_data["sdgs"]
        if goals.count() > 3:
            raise ValidationError("SDGs 最多可選擇 3 項。")
        codes = set(goals.values_list("code", flat=True))
        if "NONE" in codes and len(codes) > 1:
            raise ValidationError("選擇「無」時不得同時選擇其他 SDG。")
        return goals


class ConferenceDetailForm(BootstrapFormMixin, forms.ModelForm):
    participant_countries = forms.ModelMultipleChoiceField(
        queryset=Country.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
    )
    presentation_modes = forms.ModelMultipleChoiceField(
        queryset=ConferencePresentationMode.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
    )
    sdgs = forms.ModelMultipleChoiceField(
        queryset=SustainableDevelopmentGoal.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = ConferenceDetail
        exclude = ["id", "publication"]
        labels = {
            "conference_type": "會議屬性", "organizer": "主辦單位", "location_country": "會議地點國家",
            "location_city": "會議地點城市", "start_date": "起始日期", "end_date": "結束日期",
            "received_subsidy": "是否獲補助", "presented_paper": "是否發表論文", "remarks": "備註",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        countries = Country.objects.filter(is_active=True)
        self.fields["location_country"].queryset = countries
        self.fields["participant_countries"].queryset = countries
        self.fields["presentation_modes"].queryset = ConferencePresentationMode.objects.filter(is_active=True)
        self.fields["sdgs"].queryset = SustainableDevelopmentGoal.objects.filter(is_active=True)
        if self.instance and not self.instance._state.adding:
            self.initial["participant_countries"] = self.instance.participant_country_assignments.values_list("country", flat=True)
            self.initial["presentation_modes"] = self.instance.presentation_mode_assignments.values_list("mode", flat=True)
            self.initial["sdgs"] = self.instance.publication.sdg_assignments.values_list("goal", flat=True)

    def clean_participant_countries(self):
        countries = self.cleaned_data["participant_countries"]
        if countries.count() > 5:
            raise ValidationError("與會人員國家最多可選擇 5 個。")
        return countries

    def clean_sdgs(self):
        goals = self.cleaned_data["sdgs"]
        if goals.count() > 3:
            raise ValidationError("SDGs 最多可選擇 3 項。")
        codes = set(goals.values_list("code", flat=True))
        if "NONE" in codes and len(codes) > 1:
            raise ValidationError("選擇「無」時不得同時選擇其他 SDG。")
        return goals
