from django import forms
from .models import SourceDocument


class DocumentUploadForm(forms.Form):
    document_type = forms.ChoiceField(choices=SourceDocument.DocumentType.choices)
    file = forms.FileField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document_type"].widget.attrs["class"] = "form-select"
        self.fields["file"].widget.attrs["class"] = "form-control"
