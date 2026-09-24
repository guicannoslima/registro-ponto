from django import forms
from .models import RegistroPonto, SolicitacaoAjustePonto

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

class SolicitarCriacaoForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoAjustePonto
        fields = ['tipo', 'data_hora', 'motivo_funcionario']
        widgets = {
            'data_hora': forms.DateTimeInput(attrs={'type': 'datetime-local'})
        }

class SolicitarExclusaoForm(forms.Form):
    motivo_funcionario = forms.CharField(max_length=150)

class MotivoRejeicaoForm(forms.Form):
    motivo_rejeicao = forms.CharField(max_length=150)