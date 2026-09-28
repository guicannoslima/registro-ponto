from django import forms
from .models import RegistroPonto, SolicitacaoAjustePonto
from django.contrib.auth.models import User

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

class RelatorioForm(forms.Form):
    funcionario = forms.ModelChoiceField(queryset= User.objects.none(), required= False)
    data_inicio = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    data_fim = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    gerar_todos = forms.BooleanField(required=False)

    def __init__(self, *args, funcionarios=None, **kwargs):
        super().__init__(*args, **kwargs)
        if funcionarios is not None:
            self.fields['funcionario'].queryset = funcionarios

    def clean(self):
        gerar_todos = self.cleaned_data.get('gerar_todos')
        funcionario = self.cleaned_data.get('funcionario')
        if not gerar_todos and not funcionario:
            raise forms.ValidationError('Selecione um funcionário ou marque a opção "Gerar todos".')
        return self.cleaned_data