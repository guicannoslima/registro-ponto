# Implantação com Docker

`docker compose up -d --build` sobe a aplicação (Gunicorn) e o PostgreSQL em containers.
A cada subida, o container aplica as migrações e roda o `collectstatic`.

## Primeira subida

Pré-requisitos: [Docker](https://docs.docker.com/get-started/get-docker/) com Compose e Git.

1. Clone o repositório e crie o `.env`:

   ```bash
   git clone https://github.com/primecartorios/registro-ponto.git
   cd registro-ponto
   cp .env.example .env               # Windows (PowerShell): Copy-Item .env.example .env
   ```

2. Preencha no `.env` a `SECRET_KEY`, a `DB_PASSWORD` e os dados de e-mail.
3. Suba os containers:

   ```bash
   docker compose up -d --build
   ```

4. Crie o administrador:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

Acesse `http://localhost:8000/`. O superusuário já entra como **Administrador**.

## Variáveis de ambiente

O `.env` fica na raiz, ao lado do `manage.py`, e não é versionado. O modelo é o `.env.example`.

| Variável | Uso | Observação |
| --- | --- | --- |
| `SECRET_KEY` | Chave criptográfica do Django | Obrigatória; sem o caractere `$` |
| `DEBUG` | Modo de depuração | `False` em produção; padrão `True` |
| `ALLOWED_HOSTS` | Endereços aceitos, separados por vírgula | Padrão `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | Origens confiáveis para formulários | Com `http://` ou `https://` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Banco PostgreSQL | No Docker, também criam o banco do container |
| `DB_HOST`, `DB_PORT` | Endereço do banco | No Docker, o `compose.yaml` força `db:5432` |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Conta SMTP do Gmail | Remetente da redefinição de senha |

O Docker Compose interpreta `$` nos valores do `.env` como variável e altera o valor
lido; gere chaves só com letras, números, `-` e `_`.

Em `EMAIL_HOST_PASSWORD`, use uma [senha de app](https://support.google.com/accounts/answer/185833)
do Google, não a senha da conta. Ela exige a verificação em duas etapas ativa.

Para acessar por outro endereço, como o IP da rede ou um domínio, inclua-o em
`ALLOWED_HOSTS` e em `CSRF_TRUSTED_ORIGINS`.

## Comandos do dia a dia

| Ação | Comando |
| --- | --- |
| Parar | `docker compose down` |
| Subir novamente | `docker compose up -d` |
| Subir após alterar o código | `docker compose up -d --build` |
| Ver os logs | `docker compose logs -f web` |
| Ver o status | `docker compose ps` |
| Abrir o shell do Django | `docker compose exec web python manage.py shell` |

Os dados ficam no volume `postgres_data` e sobrevivem quando os containers são parados
ou recriados. **`docker compose down -v` apaga esse volume e todo o banco.**

## Levar os dados do banco local para o Docker

O banco do Docker é separado do PostgreSQL da máquina e começa vazio. Para copiar os dados:

1. Exporte do banco local, com o ambiente virtual ativo. O `-X utf8` evita erro de
   acentuação no Windows:

   ```bash
   python -X utf8 manage.py dumpdata --exclude contenttypes --exclude auth.permission \
     --exclude admin.logentry --exclude sessions -o dados.json
   ```

2. Copie o arquivo para o container e importe:

   ```bash
   docker compose cp dados.json web:/app/
   docker compose exec web python manage.py loaddata dados.json
   ```

3. Apague o `dados.json`: ele contém dados pessoais e hashes de senha. O arquivo já
   está no `.gitignore`.

## Imagem

O `Dockerfile` tem duas etapas: a primeira compila as dependências de
`requirements/production.txt` em wheels; a segunda instala as wheels numa imagem
`python:3.12-slim` e roda como o usuário sem privilégios `appuser`. O
`docker-entrypoint.sh` aplica as migrações e o `collectstatic` antes do Gunicorn,
com 3 workers na porta 8000. O `.dockerignore` deixa fora da imagem o `.env`, o Git,
a documentação e as ferramentas de desenvolvimento.
