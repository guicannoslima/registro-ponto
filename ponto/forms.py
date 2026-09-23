from django import forms
from .models import RegistroPonto

class RegistroManualForm(forms.ModelForm):
    class Meta:
        model = RegistroPonto
        fields = ['funcionario', 'tipo', 'data_hora']
        widgets = {
        'data_hora': forms.DateTimeInput(attrs={'type': 'datetime-local'})
        }
    motivo = forms.CharField(max_length=150)

class MotivoExclusaoForm(forms.Form):
    motivo = forms.CharField(max_length=150)