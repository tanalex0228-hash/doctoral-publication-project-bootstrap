from django import forms

from doctoral_students.models import DoctoralStudentProfile
from professors.models import Professor
from taxonomy.models import PublicationIndex, PublicationType, ResearchField


class StatisticsFilterForm(forms.Form):
    student = forms.ModelChoiceField(queryset=DoctoralStudentProfile.objects.none(), required=False, label="學生")
    year = forms.IntegerField(required=False, min_value=1, label="發表年度")
    publication_type = forms.ModelChoiceField(queryset=PublicationType.objects.none(), required=False, label="成果類型")
    publication_index = forms.ModelChoiceField(queryset=PublicationIndex.objects.none(), required=False, label="期刊／索引")
    research_field = forms.ModelChoiceField(queryset=ResearchField.objects.none(), required=False, label="研究領域")
    advisor = forms.ModelChoiceField(queryset=Professor.objects.none(), required=False, label="指導教授")
    language = forms.CharField(required=False, max_length=16, label="語言")
    author_role = forms.ChoiceField(required=False, choices=[("", "全部作者角色"), ("first_author", "學生為第一作者"), ("corresponding_author", "學生為通訊作者")], label="作者角色")
    date_basis = forms.ChoiceField(required=False, choices=[("publication_date", "發表日期"), ("accepted_date", "接受日期")], initial="publication_date", label="日期欄位")
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="起日")
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="迄日")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = DoctoralStudentProfile.objects.order_by("student_number")
        self.fields["publication_type"].queryset = PublicationType.objects.filter(is_active=True)
        self.fields["publication_index"].queryset = PublicationIndex.objects.filter(is_active=True)
        self.fields["research_field"].queryset = ResearchField.objects.filter(is_active=True)
        self.fields["advisor"].queryset = Professor.objects.filter(status=Professor.Status.ACTIVE).order_by("display_name")
        self.fields["language"].widget.attrs["placeholder"] = "例如 en"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("date_from") and cleaned_data.get("date_to") and cleaned_data["date_from"] > cleaned_data["date_to"]:
            self.add_error("date_to", "迄日不得早於起日。")
        return cleaned_data
