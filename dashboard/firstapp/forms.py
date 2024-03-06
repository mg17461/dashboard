from django import forms
from .models import EPWFile

class EPWUploadForm(forms.ModelForm):
    class Meta:
        model = EPWFile
        fields = ['file']

class CatchmentAreaForm(forms.Form):
    width = forms.FloatField(required=False, min_value=0, help_text='Enter width in meters')
    length = forms.FloatField(required=False, min_value=0, help_text='Enter length in meters')
    area = forms.FloatField(required=False, min_value=0, help_text='Enter area in square meters')