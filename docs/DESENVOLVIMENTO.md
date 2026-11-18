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
