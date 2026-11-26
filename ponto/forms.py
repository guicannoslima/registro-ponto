from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .constants import ESCOLHA_DE_BATIDA, FOTO_PERFIL_MAX_BYTES, LEMBRETES_PONTO_AJUDA, PLANILHA_MAX_BYTES
from .email import cifrar_senha
from .models import (
    ConfiguracaoEmail,
    Feriado,
    Folga,
    Funcao,
    HistoricoAlteracaoPonto,
    Jornada,
    Perfil,
    RegistroPonto,
    SolicitacaoAjustePonto,
)
from .services import configuracao_jornada, jornada_vigente, motivo_sem_expediente, vincular_jornada


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
    funcao = forms.ModelChoiceField(label = 'Função',queryset=Funcao.objects.all(), empty_label="Selecione sua função")

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
        label='CPF',
        max_length=14,
        required=False,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'data-mascara': 'cpf', 'placeholder': '000.000.000-00'}),
    )
    papel = forms.ChoiceField(label='Papel', choices=Perfil.PAPEL_CHOICES)
    funcao = forms.ModelChoiceField(label='Função', queryset=Funcao.objects.all(), required=False)
    gestor = forms.ModelChoiceField(label='Gestor', queryset=Perfil.objects.none(), required=False)
    jornada = forms.ModelChoiceField(
        label='Jornada',
        queryset=Jornada.objects.none(),
        required=False,
        empty_label='Manter regra anterior (7h45min)',
    )
    atualizar_jornada = forms.BooleanField(
        label='Aplicar novamente os horários atuais da jornada selecionada',
        required=False,
    )
    jornada_inicio = forms.DateField(
        label='Válida a partir de',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
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
        self.vinculo_atual = jornada_vigente(self.instance, timezone.localdate()) if self.instance.pk else None
        atual_id = self.vinculo_atual.jornada_id if self.vinculo_atual else None
        self.fields['jornada'].queryset = Jornada.objects.filter(Q(ativa=True) | Q(pk=atual_id))
        self.initial['jornada'] = atual_id
        self.initial['jornada_inicio'] = timezone.localdate()
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
        atual_id = self.vinculo_atual.jornada_id if self.vinculo_atual else None
        nova = dados.get('jornada')
        if ((nova.pk if nova else None) != atual_id or dados.get('atualizar_jornada')) and not dados.get(
            'jornada_inicio'
        ):
            self.add_error('jornada_inicio', 'Informe quando a nova jornada começa a valer.')
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
        atual_id = self.vinculo_atual.jornada_id if self.vinculo_atual else None
        nova = self.cleaned_data['jornada']
        if (nova.pk if nova else None) != atual_id or self.cleaned_data.get('atualizar_jornada'):
            vincular_jornada(perfil, nova, self.cleaned_data['jornada_inicio'])
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
        label='Foto de perfil',
        widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        help_text='JPEG, PNG ou WebP, até 5 MB. Fotos grandes são reduzidas automaticamente.',
    )

    def clean_foto(self):
        foto = self.cleaned_data['foto']
        if foto.size > FOTO_PERFIL_MAX_BYTES:
            raise forms.ValidationError('Escolha uma foto de até 5 MB.')
        if foto.image.format not in ('JPEG', 'PNG', 'WEBP'):
            raise forms.ValidationError('Escolha uma foto JPEG, PNG ou WebP.')
        return foto


class JornadaForm(forms.ModelForm):
    class Meta:
        model = Jornada
        fields = ['nome', 'ativa']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nomes = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        rotulos = ['Entrada', 'Saída almoço', 'Volta almoço', 'Saída café', 'Volta café', 'Saída']
        self.dias = []
        for dia, nome in enumerate(nomes):
            valores = self.instance.semana.get(str(dia), ['', '', '', '', '', ''])
            campos = []
            for indice, rotulo in enumerate(rotulos):
                chave = f'dia_{dia}_{indice}'
                self.fields[chave] = forms.TimeField(
                    label=rotulo,
                    required=False,
                    input_formats=['%H:%M'],
                    widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
                    initial=valores[indice] or None,
                )
                campos.append(self[chave])
            self.dias.append({'nome': nome, 'campos': campos})

    def clean(self):
        dados = super().clean()
        semana = {}
        for dia in range(7):
            horas = [dados.get(f'dia_{dia}_{i}') for i in range(6)]
            preenchidas = [h for h in horas if h is not None]
            if not preenchidas:
                continue
            erro = None
            if not horas[0] or not horas[5]:
                erro = 'Preencha entrada e saída ou deixe o dia inteiro vazio para folga.'
            elif bool(horas[1]) != bool(horas[2]) or bool(horas[3]) != bool(horas[4]):
                erro = 'Preencha a saída e a volta de cada intervalo.'
            elif any(a >= b for a, b in zip(preenchidas, preenchidas[1:], strict=False)):
                erro = 'Os horários precisam estar em ordem, dentro do mesmo dia.'
            if erro:
                self.add_error(f'dia_{dia}_0', erro)
            else:
                semana[str(dia)] = [h.strftime('%H:%M') if h else '' for h in horas]
        if not semana:
            raise forms.ValidationError('Cadastre ao menos um dia de trabalho.')
        self.semana = semana
        return dados

    def save(self, commit=True):
        self.instance.semana = self.semana
        return super().save(commit=commit)


class FeriadoForm(forms.ModelForm):
    class Meta:
        model = Feriado
        fields = ['data', 'nome', 'dispensa_expediente']
        widgets = {'data': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}
        labels = {'dispensa_expediente': 'Dispensa expediente na empresa'}


class FuncaoForm(forms.ModelForm):
    class Meta:
        model = Funcao
        fields = ['nome', 'lembretes_ponto']
        labels = {'nome': 'Nome da função', 'lembretes_ponto': 'Enviar lembretes de ponto'}
        help_texts = {'lembretes_ponto': LEMBRETES_PONTO_AJUDA}
        widgets = {'lembretes_ponto': forms.CheckboxInput(attrs={'aria-describedby': 'id_lembretes_ponto_ajuda'})}

    def clean_nome(self):
        nome = ' '.join(self.cleaned_data['nome'].split())
        repetida = Funcao.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk)
        if repetida.exists():
            raise forms.ValidationError('Já existe uma função com esse nome.')
        return nome


class AnoFeriadosForm(forms.Form):
    ano = forms.IntegerField(label='Ano', min_value=2000, max_value=2099)


class FuncionariosMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.username


class FolgaForm(forms.Form):
    funcionarios = FuncionariosMultipleChoiceField(
        label='Colaboradores',
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={'required': 'Escolha pelo menos um colaborador.'},
    )
    data = forms.DateField(
        label='Data',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        error_messages={'required': 'Informe a data da folga.'},
    )
    tipo = forms.ChoiceField(
        label='Tipo de folga',
        choices=Folga.TIPO_CHOICES,
        widget=forms.RadioSelect,
        initial=Folga.DISPENSA,
    )
    motivo = campo_motivo('Motivo', 'Informe o motivo da folga.')
    motivo.help_text = 'O motivo aparece no painel do colaborador.'

    def __init__(self, *args, funcionarios=None, **kwargs):
        super().__init__(*args, **kwargs)
        if funcionarios is not None:
            self.fields['funcionarios'].queryset = funcionarios

    def clean(self):
        dados = super().clean()
        pessoas, data = dados.get('funcionarios'), dados.get('data')
        if not pessoas or not data:
            return dados
        repetidas = Folga.objects.filter(funcionario__in=pessoas, data=data, ativa=True)
        if repetidas.exists():
            nomes = ', '.join(sorted(f.funcionario.get_full_name() for f in repetidas.select_related('funcionario')))
            raise forms.ValidationError(f'Já existe folga em {data:%d/%m/%Y} para: {nomes}.')
        # Feriado ou folga semanal já são dias livres: folga ali não teria efeito.
        motivos = {}
        for pessoa in pessoas:
            motivo = motivo_sem_expediente(configuracao_jornada(pessoa, data), data)
            if motivo:
                motivos[pessoa.get_full_name() or pessoa.username] = motivo
        if motivos:
            if len(set(motivos.values())) == 1:
                motivo = next(iter(motivos.values()))
                quem = ', '.join(sorted(motivos))
                raise forms.ValidationError(
                    f'{data:%d/%m/%Y} é {motivo} e já não tem expediente para {quem}. Escolha outra data.'
                )
            detalhes = '; '.join(f'{nome}: {motivo}' for nome, motivo in sorted(motivos.items()))
            raise forms.ValidationError(
                f'{data:%d/%m/%Y} já não tem expediente previsto ({detalhes}). Escolha outra data.'
            )
        return dados


class ImportarPlanilhaForm(forms.Form):
    funcionario = FuncionarioChoiceField(
        label='Colaborador',
        queryset=User.objects.none(),
        empty_label='Selecione o colaborador',
        error_messages={'required': 'Escolha para quem a planilha será importada.'},
    )
    planilha = forms.FileField(
        label='Planilha de banco de horas',
        widget=forms.FileInput(
            attrs={'accept': '.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        ),
        help_text='Arquivo .xlsx de até 5 MB, com uma aba por mês.',
        error_messages={'required': 'Escolha a planilha que será importada.'},
    )

    def __init__(self, *args, funcionarios=None, **kwargs):
        super().__init__(*args, **kwargs)
        if funcionarios is not None:
            self.fields['funcionario'].queryset = funcionarios

    def clean_planilha(self):
        planilha = self.cleaned_data['planilha']
        if not planilha.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('Envie a planilha no formato .xlsx.')
        if planilha.size > PLANILHA_MAX_BYTES:
            raise forms.ValidationError('Escolha uma planilha de até 5 MB.')
        return planilha
