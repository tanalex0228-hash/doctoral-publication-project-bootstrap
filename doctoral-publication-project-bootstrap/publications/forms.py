import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from doctoral_students.models import DoctoralStudentProfile
from .models import (
    ConferenceDetail, ConferencePresentationMode, Country, JournalArticleDetail,
    PublicationAuthor, PublicationRecord, SustainableDevelopmentGoal,
)
from taxonomy.models import PublicationIndex, PublicationType, ResearchField


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        self._require_publication_stage = kwargs.pop("require_publication_stage", False)
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
        fields = [
            "publication_type", "title", "journal_or_conference_name", "doi", "issn",
            "volume", "issue", "pages_or_article_number", "publication_stage",
            "accepted_date", "publication_date",
        ]
        labels = {
            "publication_type": "成果類型", "title": "論文篇名",
            "journal_or_conference_name": "期刊名稱／學術會議名", "doi": "DOI（數位物件識別號）",
            "issn": "國際標準期刊號 ISSN", "publication_stage": "發表進度",
            "volume": "卷", "issue": "期", "pages_or_article_number": "頁碼／文章編號",
            "accepted_date": "接受日期", "publication_date": "刊登日期",
            "indices": "索引分類", "research_fields": "研究領域",
        }
        widgets = {
            "accepted_date": forms.DateInput(attrs={"type": "date"}),
            "publication_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publication_type"].queryset = PublicationType.objects.filter(is_active=True)
        self.fields["publication_stage"].choices = [
            (PublicationRecord.PublicationStage.ACCEPTED, "已接受"),
            (PublicationRecord.PublicationStage.PUBLISHED, "已刊登"),
        ]
        self.fields["publication_stage"].required = self._require_publication_stage
        self.fields["indices"].queryset = PublicationIndex.objects.filter(is_active=True)
        self.fields["research_fields"].queryset = ResearchField.objects.filter(is_active=True)
        # These are explicitly declared fields, so Meta.labels does not apply.
        self.fields["indices"].label = "索引分類"
        self.fields["research_fields"].label = "研究領域"
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


class PublicationTypeSelectionForm(BootstrapFormMixin, forms.Form):
    publication_type = forms.ModelChoiceField(
        queryset=PublicationType.objects.none(), label="成果類型",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publication_type"].queryset = PublicationType.objects.filter(is_active=True)


class PublicationAuthorForm(BootstrapFormMixin, forms.ModelForm):
    system_student = forms.ModelChoiceField(
        queryset=DoctoralStudentProfile.objects.none(), required=False, label="本校系統學生（含學號）",
    )

    class Meta:
        model = PublicationAuthor
        fields = [
            "display_name", "is_system_student", "student_author_order", "student_author_order_reason",
            "student_author_attribute", "is_student_corresponding_author",
        ]
        labels = {
            "display_name": "姓名", "is_system_student": "是否為本校系統學生",
            "student_author_order": "學生作者序", "student_author_order_reason": "第四作者（含）以後原因",
            "student_author_attribute": "學生作者屬性", "is_student_corresponding_author": "是否為通訊作者",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["system_student"].queryset = DoctoralStudentProfile.objects.select_related("user").order_by("student_number")
        self.fields["system_student"].label_from_instance = lambda item: f"{item.display_name}（{item.student_number}）"
        if self.instance and self.instance.pk and self.instance.is_system_student and self.instance.linked_user_id:
            self.initial["system_student"] = DoctoralStudentProfile.objects.filter(user_id=self.instance.linked_user_id).first()

    def clean(self):
        cleaned = super().clean()
        is_system_student = cleaned.get("is_system_student")
        student = cleaned.get("system_student")
        if is_system_student and not student:
            self.add_error("system_student", "請選擇本校系統學生。")
        # ``linked_user`` is intentionally an internal model field rather than
        # a user-editable form field.  Set it before ModelForm's model
        # validation runs, otherwise PublicationAuthor.clean() correctly
        # rejects the record but Django cannot attach its error to a form
        # field and turns it into a 500.
        if is_system_student and student:
            self.instance.linked_user = student.user
            self.instance.display_name = student.display_name
        elif not is_system_student:
            self.instance.linked_user = None
        if not is_system_student:
            for field in ("student_author_order", "student_author_order_reason", "student_author_attribute", "is_student_corresponding_author"):
                cleaned[field] = None if field == "is_student_corresponding_author" else ""
        if is_system_student and cleaned.get("student_author_order") == PublicationAuthor.StudentAuthorOrder.FOURTH_OR_LATER and not cleaned.get("student_author_order_reason", "").strip():
            self.add_error("student_author_order_reason", "第四作者（含）以後必須填寫原因。")
        return cleaned


def publication_form_values(form):
    values = {field: form.cleaned_data[field] for field in PublicationForm.Meta.fields}
    if not values["publication_stage"]:
        values["publication_stage"] = PublicationRecord.PublicationStage.PUBLISHED
    return values, form.cleaned_data["indices"], form.cleaned_data["research_fields"]


def author_form_values(form):
    values = {field: form.cleaned_data[field] for field in PublicationAuthorForm.Meta.fields}
    student = form.cleaned_data.get("system_student")
    if student:
        values["linked_user"] = student.user
        values["display_name"] = student.display_name
    else:
        values["linked_user"] = None
    return values


class JournalArticleDetailForm(BootstrapFormMixin, forms.ModelForm):
    sdgs = forms.ModelMultipleChoiceField(
        queryset=SustainableDevelopmentGoal.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple, label="SDGs",
    )

    class Meta:
        model = JournalArticleDetail
        fields = [
            "journal_type", "international_journal_rank", "taiwan_journal_level", "custom_journal_type",
            "has_international_collaboration", "publication_medium", "paper_nature", "paper_attribute",
            "total_pages", "is_annual_representative_work", "is_peer_reviewed", "citation_count",
            "publication_country", "publication_place", "remarks",
        ]
        labels = {
            "journal_type": "期刊類型", "international_journal_rank": "SCI／SSCI 期刊排名",
            "taiwan_journal_level": "臺灣人文及社會科學期刊評比暨核心期刊收錄級別",
            "custom_journal_type": "請填寫期刊類型", "has_international_collaboration": "國際合作",
            "publication_medium": "出版媒體", "paper_nature": "論文性質", "paper_attribute": "論文屬性",
            "total_pages": "總頁數", "is_annual_representative_work": "年度代表作", "is_peer_reviewed": "是否具審查機制",
            "citation_count": "引用次數", "publication_country": "出版國", "publication_place": "出版地", "remarks": "備註",
        }
        widgets = {"remarks": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publication_country"].queryset = Country.objects.filter(is_active=True)
        self.fields["sdgs"].queryset = SustainableDevelopmentGoal.objects.filter(is_active=True)
        self.fields["taiwan_journal_level"].help_text = format_html(
            '期刊收錄查詢網址：<a href="{}" target="_blank" rel="noopener">https://reurl.cc/KkoM7m</a>',
            "https://reurl.cc/KkoM7m",
        )
        self.fields["international_journal_rank"].help_text = format_html(
            'Rank 查詢網址：<a href="{}" target="_blank" rel="noopener">https://reurl.cc/O1oAm9</a>',
            "https://reurl.cc/O1oAm9",
        )
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
        label="與會人員國家",
    )
    presentation_modes = forms.ModelMultipleChoiceField(
        queryset=ConferencePresentationMode.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
        label="發表方式／任務",
    )
    sdgs = forms.ModelMultipleChoiceField(
        queryset=SustainableDevelopmentGoal.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
        label="SDGs",
    )

    class Meta:
        model = ConferenceDetail
        fields = [
            "conference_type", "organizer", "location_country", "location_city", "start_date", "end_date",
            "received_subsidy", "presented_paper", "paper_title", "paper_nature", "paper_is_peer_reviewed",
            "paper_page_count", "has_international_collaboration", "international_collaboration_type",
            "is_scopus_indexed", "remarks",
        ]
        labels = {
            "conference_type": "會議屬性", "organizer": "主辦單位", "location_country": "會議地點國家",
            "location_city": "會議地點城市", "start_date": "起始日期", "end_date": "結束日期",
            "received_subsidy": "是否獲補助", "presented_paper": "是否發表論文",
            "paper_title": "論文篇名", "paper_nature": "論文性質", "paper_is_peer_reviewed": "論文是否有審查機制",
            "paper_page_count": "頁數", "has_international_collaboration": "是否國際合作",
            "international_collaboration_type": "國際合作類型", "is_scopus_indexed": "是否 Scopus 收錄",
            "remarks": "備註",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "paper_page_count": forms.NumberInput(attrs={"min": 1}),
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

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("presented_paper"):
            cleaned["paper_title"] = ""
            cleaned["paper_nature"] = ""
            cleaned["paper_is_peer_reviewed"] = False
            cleaned["paper_page_count"] = None
            cleaned["has_international_collaboration"] = False
            cleaned["international_collaboration_type"] = ""
            cleaned["is_scopus_indexed"] = False
        elif not cleaned.get("has_international_collaboration"):
            cleaned["international_collaboration_type"] = ""
        return cleaned

    def clean_sdgs(self):
        goals = self.cleaned_data["sdgs"]
        if goals.count() > 3:
            raise ValidationError("SDGs 最多可選擇 3 項。")
        codes = set(goals.values_list("code", flat=True))
        if "NONE" in codes and len(codes) > 1:
            raise ValidationError("選擇「無」時不得同時選擇其他 SDG。")
        return goals
