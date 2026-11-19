from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .constants import ESCOLHA_DE_BATIDA, FOTO_PERFIL_MAX_BYTES
from .email import cifrar_senha
from .models import ConfiguracaoEmail, Funcao, HistoricoAlteracaoPonto, Perfil, RegistroPonto, SolicitacaoAjustePonto


class FuncionarioChoiceField(forms.ModelChoiceField):
    """Mostra o nome completo do colaborador, e não o nome de usuário."""

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
        label='Colaborador', queryset=User.objects.none(), empty_label='Selecione o colaborador'
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
        label='Colaborador', queryset=User.objects.none(), required=False, empty_label='Toda a equipe'
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
        label='Colaborador', empty_label='Selecione um colaborador', queryset=User.objects.none(), required=False
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
            raise forms.ValidationError('Selecione um colaborador ou marque "Gerar para toda a equipe".')
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

class UsuarioAdministracaoForm(forms.ModelForm):
    first_name = forms.CharField(label='Nome', max_length=150)
    last_name = forms.CharField(label='Sobrenome', max_length=150)
    email = forms.EmailField(label='E-mail')
    cpf = forms.CharField(
        label='CPF', max_length=14, required=False,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'data-mascara': 'cpf', 'placeholder': '000.000.000-00'}),
    )
    papel = forms.ChoiceField(label='Papel', choices=Perfil.PAPEL_CHOICES)
    funcao = forms.ModelChoiceField(label='Função', queryset=Funcao.objects.all(), required=False)
    gestor = forms.ModelChoiceField(label='Gestor', queryset=Perfil.objects.none(), required=False)
    senha = forms.CharField(
        label='Senha', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}), required=False, strip=False
    )
    confirmar_senha = forms.CharField(
        label='Confirmar senha',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False,
        strip=False,
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'is_active']
        labels = {'username': 'Nome de usuário', 'is_active': 'Usuário ativo'}
        help_texts = {'username': 'Usado para entrar no sistema.'}

    def __init__(self, *args, administrador, **kwargs):
        super().__init__(*args, **kwargs)
        self.administrador = administrador
        self.fields['gestor'].queryset = (
            Perfil.objects.filter(
                papel=Perfil.PAPEL_GESTOR,
                user__is_active=True,
            )
            .exclude(user_id=self.instance.pk)
            .select_related('user')
        )
        if self.instance.pk:
            perfil = self.instance.perfil
            for nome in ('cpf', 'papel', 'funcao', 'gestor'):
                self.initial[nome] = getattr(perfil, nome)
            self.fields['senha'].help_text = 'Deixe em branco para manter a senha atual.'
        else:
            self.fields['senha'].required = True
            self.fields['confirmar_senha'].required = True
            self.initial['is_active'] = True

    def clean_cpf(self):
        informado = self.cleaned_data['cpf'].strip()
        cpf = ''.join(c for c in informado if c.isdigit())
        if informado and len(cpf) != 11:
            raise forms.ValidationError('Informe um CPF com 11 dígitos.')
        if cpf and Perfil.objects.filter(cpf=cpf).exclude(user_id=self.instance.pk).exists():
            raise forms.ValidationError('Este CPF já está em uso.')
        return cpf or None

    def clean(self):
        dados = super().clean()
        if dados.get('senha') != dados.get('confirmar_senha'):
            self.add_error('confirmar_senha', 'As senhas não coincidem.')
        if self.instance.pk == self.administrador.pk:
            if not dados.get('is_active'):
                self.add_error('is_active', 'Você não pode desativar sua própria conta.')
            if dados.get('papel') != Perfil.PAPEL_ADMIN:
                self.add_error('papel', 'Mantenha sua conta como Administrador.')
        if self.instance.is_superuser and dados.get('papel') != Perfil.PAPEL_ADMIN:
            self.add_error('papel', 'Um superusuário precisa manter o papel de Administrador.')
        return dados

    def _post_clean(self):
        super()._post_clean()
        if senha := self.cleaned_data.get('senha'):
            try:
                validate_password(senha, self.instance)
            except forms.ValidationError as exc:
                self.add_error('senha', exc)

    @transaction.atomic
    def save(self):
        usuario = super().save(commit=False)
        if senha := self.cleaned_data.get('senha'):
            usuario.set_password(senha)
        usuario.save()
        perfil = usuario.perfil
        for campo in ('cpf', 'papel', 'funcao', 'gestor'):
            setattr(perfil, campo, self.cleaned_data[campo])
        perfil.save()
        return usuario


class ConfiguracaoEmailForm(forms.ModelForm):
    senha = forms.CharField(
        label='Senha SMTP',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False,
        strip=False,
        help_text=('Deixe em branco para manter a senha atual. Use a senha de aplicativo do provedor, se exigida.'),
    )
    limpar_senha = forms.BooleanField(label='Remover a senha de autenticação atual', required=False)

    class Meta:
        model = ConfiguracaoEmail
        fields = ['servidor', 'porta', 'usuario', 'seguranca', 'remetente']
        labels = {
            'servidor': 'Servidor SMTP',
            'porta': 'Porta',
            'usuario': 'Usuário de autenticação',
            'seguranca': 'Segurança da conexão',
            'remetente': 'E-mail remetente',
        }

    def clean_porta(self):
        porta = self.cleaned_data['porta']
        if not 1 <= porta <= 65535:
            raise forms.ValidationError('Informe uma porta entre 1 e 65535.')
        return porta

    def clean_servidor(self):
        servidor = self.cleaned_data['servidor'].strip()
        if any(c.isspace() for c in servidor) or '/' in servidor or ':' in servidor:
            raise forms.ValidationError('Informe apenas o nome ou IP do servidor, sem protocolo nem porta.')
        return servidor

    def clean(self):
        dados = super().clean()
        if dados.get('senha') and dados.get('limpar_senha'):
            self.add_error('senha', 'Informe uma nova senha ou marque a remoção, sem combinar as duas opções.')
        return dados

    def save(self, *, administrador):
        configuracao = super().save(commit=False)
        if self.cleaned_data['limpar_senha']:
            configuracao.senha_criptografada = ''
        elif senha := self.cleaned_data.get('senha'):
            configuracao.senha_criptografada = cifrar_senha(senha)
        elif not configuracao.senha_criptografada and self.instance._state.adding:
            configuracao.senha_criptografada = cifrar_senha(settings.EMAIL_HOST_PASSWORD)
        configuracao.pk = 1
        configuracao.atualizado_por = administrador
        configuracao.save()
        return configuracao


class TesteEmailForm(forms.Form):
    destinatario = forms.EmailField(label='Enviar teste para')


class FotoPerfilForm(forms.Form):
    foto = forms.ImageField(
        label='Foto de perfil', widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        help_text='JPEG, PNG ou WebP, até 5 MB. Fotos grandes são reduzidas automaticamente.',
    )

    def clean_foto(self):
        foto = self.cleaned_data['foto']
        if foto.size > FOTO_PERFIL_MAX_BYTES:
            raise forms.ValidationError('Escolha uma foto de até 5 MB.')
        if foto.image.format not in ('JPEG', 'PNG', 'WEBP'):
            raise forms.ValidationError('Escolha uma foto JPEG, PNG ou WebP.')
        return foto
