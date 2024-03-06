from django import forms
from .models import EPWFile

class EPWUploadForm(forms.ModelForm):
    class Meta:
        model = EPWFile
        fields = ['file']
