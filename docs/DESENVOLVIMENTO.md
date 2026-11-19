# Desenvolvimento

Rode o projeto localmente com Python 3.12+, PostgreSQL e um ambiente virtual em `.venv`.
Para subir tudo em containers, sem instalar Python nem PostgreSQL, veja [Implantação](IMPLANTACAO.md).

## Preparação

1. Clone o repositório e crie o ambiente virtual:

   ```bash
   git clone https://github.com/primecartorios/registro-ponto.git
   cd registro-ponto
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements/development.txt
   ```

2. Crie o banco no PostgreSQL:

   ```sql
   CREATE DATABASE registro_ponto;
   ```

3. Copie o `.env.example` para `.env` e preencha os valores
   ([variáveis](IMPLANTACAO.md#variáveis-de-ambiente)). Para desenvolver, use `DEBUG=True`.
   Para gerar a `SECRET_KEY`:

   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

4. Aplique as migrações, crie o administrador e inicie o servidor:

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```

Acesse `http://127.0.0.1:8000/`. O superusuário já entra como **Administrador**.

## PyCharm

A pasta `.idea/` não é versionada; configure o projeto em **Settings**:

| Campo | Valor |
| --- | --- |
| **Python Interpreter** | `<repositório>/.venv/bin/python` |
| **Django** › **Enable Django Support** | ✅ |
| **Django project root** | `<repositório>` |
| **Settings** | `registro_ponto/settings.py` |
| **Manage script** | `manage.py` |

Não é preciso informar variáveis de ambiente: o `settings.py` lê o `.env` da raiz.
Crie as configurações em **Run** › **Edit Configurations** › **+**:

| Nome | Tipo | Parâmetros |
| --- | --- | --- |
| `Django runserver` | **Django Server** | Host `127.0.0.1`, porta `8000` |
| `Django migrate` | **Python**, script `manage.py` | `migrate` |
| `Django makemigrations` | **Python**, script `manage.py` | `makemigrations` |
| `Django createsuperuser` | **Python**, script `manage.py` | `createsuperuser`, com **Emulate terminal** marcado |

Todas aceitam **Debug**, com breakpoints.

## Dependências

| Arquivo | Conteúdo | Usado por |
| --- | --- | --- |
| `requirements/base.txt` | Django, PostgreSQL, PDF, estáticos e demais dependências comuns | Todos os ambientes |
| `requirements/development.txt` | `base.txt` mais o Ruff | Ambiente local |
| `requirements/production.txt` | `base.txt` mais o Gunicorn | Imagem Docker |

O Django fica na série LTS com `~=` (`Django~=5.2.19`), que aceita só correções 5.2.x
([decisão](DECISOES.md#django-52-lts--18112026)). As demais dependências têm versão fixa.

## Lint e formatação

O [Ruff](https://docs.astral.sh/ruff/) usa as regras do `pyproject.toml`: linhas de até
120 colunas, aspas simples e as migrações fora da verificação.

```bash
ruff check .
ruff format --check .
```

No PyCharm, ative o plugin **Ruff** em **Settings** › **Plugins** e aponte para
`.venv/bin/ruff`. **Limitação conhecida:** o código anterior ao Ruff ainda tem avisos,
como linhas longas em `views.py`, `urls.py` e `forms.py` ([Roadmap](ROADMAP.md)).

## Migrações

Gere migrações com `python manage.py makemigrations` e confira, antes do commit, que
nenhuma ficou pendente:

```bash
python manage.py makemigrations --check --dry-run
```

Migrações de dados usam `RunPython` com modelos históricos (`apps.get_model`), como a
`0006_criar_perfil_usuarios_sem_perfil`.

## Preparar o reconhecimento facial

Depois de instalar as dependências do ambiente, rode:

```bash
python manage.py migrate
python manage.py preparar_facial
```

O segundo comando baixa YuNet e SFace do repositório oficial OpenCV e confere o SHA-256
antes de salvar em `modelos_faciais/` (ignorado pelo Git). Reexecutar conserva os arquivos
já verificados. `FACIAL_MODELS_DIR` permite escolher outro diretório. Não há download
em requisições; modelos ausentes retornam uma orientação sem gravar ponto.

O processamento usa `opencv-python-headless` e NumPy no servidor, com imagens limitadas a
1 MB e 1280 × 1280 pixels. O navegador captura até 640 × 480. O vetor normalizado tem
128 posições; o limiar de similaridade de cosseno é 0,5, com margem mínima de 0,08 entre
candidatos no terminal. Esses valores estão em `ponto/constants.py`; a referência técnica
é o [tutorial oficial de YuNet e SFace](https://docs.opencv.org/4.x/d0/dd4/tutorial_dnn_face.html).
O limiar exige validação no ambiente de uso; não representa uma garantia de precisão.

`ponto/facial.py` processa e compara rostos; `ponto/views.py` controla os três fluxos.
`ponto/services.py` grava as batidas comum e facial com bloqueio transacional por usuário
para que pedidos simultâneos respeitem o intervalo mínimo. Os vetores ficam na tabela
`CadastroFacial` e não são expostos por URLs ou pelo admin.

## Organização dos módulos e configuração de e-mail

Formulários ficam em `ponto/forms.py`, views em `ponto/views.py` e exceções de domínio
em `ponto/exceptions.py`, conforme solicitado pelo usuário. `_lock` e `_motor` continuam
em `facial.py`: são estado do processamento, não exceções.
`ponto/services.py` concentra regras e consultas: sequência e gravação de batidas, linha
do dia, situação, preparação do cartão ponto e os auxiliares de acesso `_gestor` e `_pessoas`.
`ponto/utils.py` concentra formatação (`data_por_extenso`, `dia_curto`, `rotulo_do_dia`,
`formatar_saldo`, `hhmm`) e auxiliares HTTP (`_limitar_captura`, `_erro`, `_presenca_facial`
e `_resposta_registro_facial`). Os serviços
podem usar os formatadores; os utilitários não consultam o banco nem importam os serviços.
Todos os testes ficam em `ponto/tests.py`.

`registrar_ponto_facial`, em `services.py`, consulta os cadastros permitidos, reconhece
o rosto, verifica a presença anterior no terminal e registra a batida. Recebe usuário,
imagem e dados simples da presença anterior; devolve `pessoa_id`, `registrado` e `mensagem`.
Não recebe `request` ou sessão e não retorna `JsonResponse` nem códigos HTTP. A ausência
de cadastro gera `CadastroFacialAusente`, definida em `exceptions.py`.

As views pessoal e de terminal chamam esse serviço. Os utilitários convertem a presença
armazenada na sessão para dados do serviço e adaptam seu resultado para HTTP, preservando
as respostas existentes e o formato da sessão. Sem rosto, a view do terminal limpa a
presença anterior. O GET pessoal consulta `tem_cadastro_facial` para montar a tela.

`ponto/email.py` estende o [backend SMTP do Django](https://docs.djangoproject.com/en/5.2/topics/email/).
Até haver `ConfiguracaoEmail` no banco, utiliza as definições atuais de `settings.py`.
Depois, carrega servidor, porta, segurança, autenticação e remetente salvos pela administração
a cada conexão, inclusive para recuperação de senha. Não exige reiniciar o servidor.

A senha SMTP é cifrada com [Fernet](https://cryptography.io/en/latest/fernet/), usando uma
chave derivada da `SECRET_KEY`. Preserve a chave ao restaurar backups; após trocá-la, salve
novamente a senha SMTP. A migração `0008` cria a tabela, sem gravar credenciais do ambiente.

## Foto de perfil e confirmação visual

`Perfil.foto` guarda a foto escolhida pelo colaborador, com a migração `0010`. O formulário
valida JPEG, PNG ou WebP, até 5 MB e 16 milhões de pixels. `salvar_foto_perfil` normaliza
orientação e enquadramento para JPEG de 512 × 512, usando nome aleatório, e remove o arquivo
anterior após confirmar a alteração no banco. Os arquivos ficam em `MEDIA_ROOT` (`media/`,
ignorado pelo Git).

`/perfil/` permite alterar somente a foto do usuário logado. `/perfil/foto/<id>/` entrega
imagens pelo controle de acesso do sistema, com resposta privada sem cache; não há rota
pública para a pasta de mídia. A sessão do terminal só permite a foto da pessoa confirmada
e exige um gestor ativo e autorizado.

O serviço retorna **PONTO REGISTRADO - PRIMEIRO NOME**, o nome completo e a indicação de
foto. O adaptador HTTP monta a URL privada e indica se é uma confirmação repetida.
`camera.js` exibe foto ou avatar genérico por `CONFIRMACAO_PONTO_MS` (3000), contado após
o carregamento da imagem. Durante esse período não envia outra captura; respostas repetidas
do terminal não reabrem a confirmação. Sem conseguir carregar a foto, usa a imagem genérica.
