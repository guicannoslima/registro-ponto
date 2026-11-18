from django import forms
from django.contrib.auth.models import User

from .constants import ESCOLHA_DE_BATIDA
from .models import Funcao, HistoricoAlteracaoPonto, Perfil, RegistroPonto, SolicitacaoAjustePonto


class FuncionarioChoiceField(forms.ModelChoiceField):
    """Mostra o nome completo do funcionário, e não o nome de usuário."""

    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.username


def campo_data_hora():
    return forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')


def campo_motivo(label, mensagem):
    return forms.CharField(
        max_length=150,
        label=label,
        widget=forms.Textarea(attrs={'rows': 3}),
        error_messages={'required': mensagem},
    )


class RegistroManualForm(forms.ModelForm):
    funcionario = FuncionarioChoiceField(
        label='Funcionário', queryset=User.objects.none(), empty_label='Selecione o funcionário'
    )

    def __init__(self, *args, funcionarios=None, **kwargs):
        super().__init__(*args, **kwargs)
        if funcionarios is not None:
            self.fields['funcionario'].queryset = funcionarios
        self.fields['tipo'].choices = ESCOLHA_DE_BATIDA

    class Meta:
        model = RegistroPonto
        fields = ['funcionario', 'tipo', 'data_hora']
        widgets = {'data_hora': campo_data_hora()}
        labels = {
            'tipo': 'Tipo de batida',
            'data_hora': 'Data e hora',
        }

    motivo = campo_motivo('Motivo', 'Informe o motivo do lançamento.')
    motivo.help_text = 'O motivo fica registrado no histórico de alterações.'


class MotivoExclusaoForm(forms.Form):
    motivo = campo_motivo('Motivo da exclusão', 'Informe o motivo da exclusão.')


class SolicitarCriacaoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].choices = ESCOLHA_DE_BATIDA
        self.fields['tipo'].required = True
        self.fields['data_hora'].required = True

    class Meta:
        model = SolicitacaoAjustePonto
        fields = ['tipo', 'data_hora', 'motivo_funcionario']
        widgets = {
            'data_hora': campo_data_hora(),
            'motivo_funcionario': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'tipo': 'Tipo de batida',
            'data_hora': 'Data e hora',
            'motivo_funcionario': 'Motivo',
        }


class SolicitarExclusaoForm(forms.Form):
    motivo_funcionario = campo_motivo('Motivo', 'Informe o motivo do pedido.')


class MotivoRejeicaoForm(forms.Form):
    motivo_rejeicao = campo_motivo('Motivo da rejeição', 'Informe o motivo da rejeição para continuar.')


class HistoricoFiltroForm(forms.Form):
    ACOES = [('', 'Todas')] + list(HistoricoAlteracaoPonto.ACAO_CHOICES)

    funcionario = FuncionarioChoiceField(
        label='Funcionário', queryset=User.objects.none(), required=False, empty_label='Toda a equipe'
    )
    acao = forms.ChoiceField(label='Ação', choices=ACOES, required=False)
    de = forms.DateField(label='De', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    ate = forms.DateField(label='Até', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, funcionarios=None, **kwargs):
        super().__init__(*args, **kwargs)
        if funcionarios is not None:
            self.fields['funcionario'].queryset = funcionarios

class RelatorioForm(forms.Form):
    funcionario = FuncionarioChoiceField(
        label='Funcionário', empty_label='Selecione um funcionário', queryset=User.objects.none(), required=False
    )
    data_inicio = forms.DateField(label = 'Data inicial',widget=forms.DateInput(attrs={'type': 'date'}))
    data_fim = forms.DateField(label = 'Data final', widget=forms.DateInput(attrs={'type': 'date'}))
    gerar_todos = forms.BooleanField(label = 'Gerar para toda a equipe', required=False)

    def __init__(self, *args, funcionarios=None, permite_todos=True, **kwargs):
        super().__init__(*args, **kwargs)
        if funcionarios is not None:
            self.fields['funcionario'].queryset = funcionarios
        if not permite_todos:
            del self.fields['gerar_todos']

    def clean(self):
        gerar_todos = self.cleaned_data.get('gerar_todos')
        funcionario = self.cleaned_data.get('funcionario')
        data_inicio = self.cleaned_data.get('data_inicio')
        data_fim = self.cleaned_data.get('data_fim')
        if not gerar_todos and not funcionario:
            raise forms.ValidationError('Selecione um funcionário ou marque "Gerar para toda a equipe".')
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