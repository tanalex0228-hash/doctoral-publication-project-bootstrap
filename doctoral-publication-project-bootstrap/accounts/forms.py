from django import forms
from django.contrib.admin.helpers import ActionForm


class AccountImportForm(forms.Form):
    workbook = forms.FileField(label="Excel (.xlsx) 匯入檔")

    def clean_workbook(self):
        workbook = self.cleaned_data["workbook"]
        if not workbook.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("請上傳 .xlsx Excel 檔案。")
        return workbook


class UserRoleActionForm(ActionForm):
    role_slug = forms.ChoiceField(
        label="設定權限群組為",
        choices=(("", "請選擇權限群組"), ("advisor", "教師"), ("student", "學生"), ("admin", "管理員")),
        required=False,
    )
