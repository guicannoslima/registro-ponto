from django import forms
from .models import Funcao, Perfil, RegistroPonto, SolicitacaoAjustePonto
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
    funcionario = forms.ModelChoiceField(label= 'Funcionário', empty_label= 'Selecione um funcionário', queryset= User.objects.none(), required= False)
    data_inicio = forms.DateField(label = 'Data inicial',widget=forms.DateInput(attrs={'type': 'date'}))
    data_fim = forms.DateField(label = 'Data final', widget=forms.DateInput(attrs={'type': 'date'}))
    gerar_todos = forms.BooleanField(label = 'Gerar relatórios de todos os funcionários', required=False)

    def __init__(self, *args, funcionarios=None, **kwargs):
        super().__init__(*args, **kwargs)
        if funcionarios is not None:
            self.fields['funcionario'].queryset = funcionarios

    def clean(self):
        gerar_todos = self.cleaned_data.get('gerar_todos')
        funcionario = self.cleaned_data.get('funcionario')
        data_inicio = self.cleaned_data.get('data_inicio')
        data_fim = self.cleaned_data.get('data_fim')
        if not gerar_todos and not funcionario:
            raise forms.ValidationError('Selecione um funcionário ou marque a opção "Gerar relatórios de todos os funcionários".')
        if data_inicio and data_fim and data_fim < data_inicio:
            raise forms.ValidationError('A data final não pode ser anterior à data inicial.')
        return self.cleaned_data

class CadastroForm(forms.Form):
    username = forms.CharField(label = 'Usuário', max_length=150)
    password = forms.CharField(label = 'Senha', widget=forms.PasswordInput)
    password2 = forms.CharField(label = 'Confirmar Senha', widget=forms.PasswordInput)
    first_name = forms.CharField(label = 'Nome', max_length=150)
    last_name = forms.CharField(label = 'Sobrenome', max_length=150)
    cpf = forms.CharField(label = 'CPF', max_length=14)
    email = forms.EmailField(label = 'E-mail')
    funcao = forms.ModelChoiceField(label = 'Função',queryset=Funcao.objects.all(), empty_label="Selecione suas função")

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        resultado = ''
        
        for caractere in cpf:
            if caractere.isdigit():
                resultado += caractere
        if len(resultado) != 11:
            raise forms.ValidationError('CPF inválido. Deve ter 11 dígitos.')      
        return resultado

    def clean(self):
        if self.cleaned_data.get('password') != self.cleaned_data.get('password2'):
            raise forms.ValidationError('As senhas não coincidem.')
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este nome de usuário já está em uso.')
        if Perfil.objects.filter(cpf=self.cleaned_data.get('cpf')).exists():
            raise forms.ValidationError('Este CPF já está em uso.') 
        return self.cleaned_data