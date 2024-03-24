from django import forms
from .models import EPWFile

class EPWUploadForm(forms.ModelForm):
    class Meta:
        model = EPWFile
        fields = ['file']


class CatchmentAreaForm(forms.Form):
    width = forms.FloatField(min_value=0.0, required=True, widget=forms.NumberInput(attrs={'class': 'input-class', 'placeholder': 'Enter value...'}))
    length = forms.FloatField(min_value=0.0, required=True, widget=forms.NumberInput(attrs={'class': 'input-class', 'placeholder': 'Enter value...'}))
    catchment_area = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'input-class', 'placeholder': ''}))

class PVToolForm(forms.Form):

    # Choices for the new dropdown
    ROOF_TYPES = (
        ('flat', 'Flat roof'),
        ('pitched', 'Pitched roof'),  
    )
    # Roof dimensions
    roof_length = forms.FloatField(label='Roof length (m):', min_value=0)
    roof_width = forms.FloatField(label='Roof width (m):', min_value=0)
    roof_type = forms.ChoiceField(choices=ROOF_TYPES, label='Roof Type')

    # PV properties
    module_efficiency = forms.FloatField(label='Module efficiency (%):', initial=18, min_value=0, max_value=100)
    pv_width = forms.FloatField(label='PV width (m):',initial=1.032, min_value=0)
    pv_height = forms.FloatField(label='PV height (m):',initial=1.872, min_value=0)
    inverter_efficiency = forms.FloatField(label='Inverter efficiency (%):', initial=96, min_value=0, max_value=100)
    other_losses = forms.FloatField(label='Other losses (%):', initial=14, min_value=0, max_value=100)
