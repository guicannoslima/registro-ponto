#!/usr/bin/env bash
# Instala o Registro de Ponto num Ubuntu Server 24.04: Docker, projeto, Nginx, HTTPS, administrador e backup.
#
# Uso, como o usuário prime (que precisa de sudo):
#   bash instalar.sh                    (primeira vez, baixado para a pasta pessoal)
#   bash /opt/registro-ponto/scripts/instalar.sh   (para atualizar)
#
# Rodar de novo atualiza o código e reaplica a configuração, sem trocar senhas nem apagar dados.
# As respostas podem vir de variáveis de ambiente com os mesmos nomes das perguntas (DOMINIO, GITHUB_USUARIO...).
set -euo pipefail

# O bloco { ... } é lido inteiro antes de rodar: o git pull pode atualizar este arquivo no meio da execução.
{

REPOSITORIO="github.com/primecartorios/registro-ponto.git"
PASTA=/opt/registro-ponto
BACKUPS=/var/backups/registro-ponto
USUARIO=$(id -un)

passo() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
aviso() { printf '\033[1;33mAviso:\033[0m %s\n' "$*"; }
erro() { printf '\033[1;31mErro:\033[0m %s\n' "$*" >&2; exit 1; }

perguntar() {  # perguntar VARIAVEL "Pergunta" [padrão]
    local variavel=$1 texto=$2 padrao=${3:-} resposta
    [ -n "${!variavel:-}" ] && return 0
    read -r -p "$texto${padrao:+ [$padrao]}: " resposta
    printf -v "$variavel" '%s' "${resposta:-$padrao}"
}

perguntar_segredo() {  # perguntar_segredo VARIAVEL "Pergunta" (não mostra o que é digitado)
    local variavel=$1 texto=$2 resposta
    [ -n "${!variavel:-}" ] && return 0
    read -r -s -p "$texto: " resposta
    echo
    printf -v "$variavel" '%s' "$resposta"
}

gerar() {  # gerar TAMANHO: só letras, números, - e _ (o Docker Compose interpreta $ no .env)
    python3 -c "import secrets, string; a = string.ascii_letters + string.digits + '-_'; \
print(''.join(secrets.choice(a) for _ in range($1)))"
}

codificar() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }

definir() {  # definir CHAVE VALOR no .env
    if grep -q "^$1=" .env; then
        sed -i "s|^$1=.*|$1=$2|" .env
    else
        echo "$1=$2" >> .env
    fi
}

# ---------------------------------------------------------------- verificações

[ "$(id -u)" -ne 0 ] || erro "Rode como o usuário prime, não como root."
# shellcheck source=/dev/null
. /etc/os-release
[ "${ID:-}" = ubuntu ] || erro "Este script foi feito para Ubuntu Server 24.04."
[ "${VERSION_ID:-}" = "24.04" ] || aviso "Feito para Ubuntu 24.04; este servidor é ${PRETTY_NAME:-desconhecido}."
echo "O sudo vai pedir a senha do $USUARIO."
sudo -v || erro "O usuário $USUARIO precisa de permissão de sudo."
# Mantém o sudo ativo enquanto o script roda (o build pode passar de 5 minutos).
while true; do sudo -n true; sleep 50; kill -0 "$$" 2>/dev/null || exit; done &

PRIMEIRA_INSTALACAO=0
[ -f "$PASTA/.env" ] || PRIMEIRA_INSTALACAO=1

# ---------------------------------------------------------------- perguntas

passo "Dados da instalação"
IP_DETECTADO=$(hostname -I | awk '{print $1}')
perguntar DOMINIO "Domínio do sistema (ex.: ponto.empresa.com.br)"
[ -n "$DOMINIO" ] || erro "Informe o domínio."
perguntar IP_SERVIDOR "IP interno deste servidor" "$IP_DETECTADO"

if [ ! -d "$PASTA/.git" ]; then
    echo "O GitHub não aceita a senha da conta para clonar: use um token pessoal com leitura do repositório."
    perguntar GITHUB_USUARIO "Usuário do GitHub"
    perguntar_segredo GITHUB_TOKEN "Token do GitHub"
    [ -n "$GITHUB_USUARIO" ] && [ -n "$GITHUB_TOKEN" ] || erro "Informe usuário e token do GitHub."
fi

if [ "$PRIMEIRA_INSTALACAO" = 1 ]; then
    perguntar EMAIL_HOST_USER "Conta Gmail que envia os e-mails do sistema"
    perguntar_segredo EMAIL_HOST_PASSWORD "Senha de app dessa conta Gmail (16 letras)"
    EMAIL_HOST_PASSWORD=${EMAIL_HOST_PASSWORD// /}
    perguntar ADMIN_USUARIO "Usuário do administrador do sistema" "admin"
    perguntar ADMIN_EMAIL "E-mail do administrador"
    while [ -z "${ADMIN_SENHA:-}" ]; do
        perguntar_segredo ADMIN_SENHA "Senha do administrador"
        perguntar_segredo ADMIN_SENHA_CONFIRMACAO "Repita a senha"
        if [ "$ADMIN_SENHA" != "$ADMIN_SENHA_CONFIRMACAO" ]; then
            aviso "As senhas não conferem. Digite de novo."
            ADMIN_SENHA="" ADMIN_SENHA_CONFIRMACAO=""
        fi
    done
    for valor in "$EMAIL_HOST_USER" "$EMAIL_HOST_PASSWORD"; do
        case $valor in *'$'*) erro "Os valores do .env não podem ter o caractere \$.";; esac
    done
fi

CERTIFICADO=/etc/letsencrypt/live/$DOMINIO/fullchain.pem
if ! sudo test -f "$CERTIFICADO"; then
    echo "O HTTPS é obrigatório para a câmera. Com IP interno, o certificado é validado pelo DNS da Cloudflare."
    echo "Crie na Cloudflare um token de API com a permissão Zona > DNS > Editar para o domínio."
    perguntar_segredo CLOUDFLARE_TOKEN "Token da API da Cloudflare (Enter para instalar só com HTTP)"
    if [ -n "$CLOUDFLARE_TOKEN" ]; then
        perguntar EMAIL_CERTIFICADO "E-mail para avisos do certificado" "${ADMIN_EMAIL:-}"
    fi
fi

# ---------------------------------------------------------------- sistema

passo "Atualizando o sistema"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get -y \
    -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade
sudo timedatectl set-timezone America/Sao_Paulo
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git curl ca-certificates python3 nginx ufw unattended-upgrades

passo "Instalando o Docker"
if ! command -v docker > /dev/null; then
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
        docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
    echo "Docker já instalado: $(docker --version)"
fi
sudo systemctl enable --now docker containerd
sudo usermod -aG docker "$USUARIO"
DOCKER="sudo docker"

passo "Configurando o firewall (SSH, HTTP e HTTPS)"
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

# ---------------------------------------------------------------- projeto

passo "Baixando o projeto em $PASTA"
if [ ! -d "$PASTA/.git" ]; then
    sudo mkdir -p "$PASTA"
    sudo chown "$USUARIO:$USUARIO" "$PASTA"
    URL="https://$(codificar "$GITHUB_USUARIO"):$(codificar "$GITHUB_TOKEN")@$REPOSITORIO"
    git clone "$URL" "$PASTA" || erro "Não foi possível clonar. Confira o usuário e o token do GitHub."
else
    git -C "$PASTA" pull --ff-only || erro "Não foi possível atualizar o código. Veja a mensagem do git acima."
fi
# O token fica na URL do repositório, para as próximas atualizações: só o dono lê.
chmod 600 "$PASTA/.git/config"
cd "$PASTA"

passo "Configurando o .env"
if [ "$PRIMEIRA_INSTALACAO" = 1 ]; then
    cat > .env <<EOF
SECRET_KEY=$(gerar 64)
DEBUG=False
ALLOWED_HOSTS=
CSRF_TRUSTED_ORIGINS=

DB_NAME=registro_ponto
DB_USER=registro_ponto
DB_PASSWORD=$(gerar 32)
DB_HOST=localhost
DB_PORT=5432

EMAIL_HOST_USER=$EMAIL_HOST_USER
EMAIL_HOST_PASSWORD=$EMAIL_HOST_PASSWORD
EOF
    chmod 600 .env
else
    echo ".env existente preservado (senhas e chave não mudam)."
fi
definir DEBUG False
definir ALLOWED_HOSTS "$DOMINIO,$IP_SERVIDOR,localhost,127.0.0.1"
definir CSRF_TRUSTED_ORIGINS "https://$DOMINIO,http://$DOMINIO,http://$IP_SERVIDOR"

# A porta 8000 fica só para o Nginx deste servidor: o Docker ignora as regras do ufw.
cat > compose.override.yaml <<'EOF'
services:
  web:
    ports: !override
      - "127.0.0.1:8000:8000"
EOF
grep -qx "compose.override.yaml" .git/info/exclude 2>/dev/null || echo "compose.override.yaml" >> .git/info/exclude

passo "Construindo e subindo os containers (alguns minutos na primeira vez)"
$DOCKER compose up -d --build

echo "Aguardando a aplicação responder..."
for _ in $(seq 60); do
    if curl -fsS -o /dev/null -H "Host: $DOMINIO" http://127.0.0.1:8000/login/; then
        PRONTA=1
        break
    fi
    sleep 5
done
if [ -z "${PRONTA:-}" ]; then
    $DOCKER compose logs --tail=60 web
    erro "A aplicação não respondeu em 5 minutos. Veja os logs acima."
fi
echo "Aplicação no ar."

if [ "$PRIMEIRA_INSTALACAO" = 1 ]; then
    passo "Criando o administrador $ADMIN_USUARIO"
    $DOCKER compose exec -T \
        -e DJANGO_SUPERUSER_USERNAME="$ADMIN_USUARIO" \
        -e DJANGO_SUPERUSER_EMAIL="$ADMIN_EMAIL" \
        -e DJANGO_SUPERUSER_PASSWORD="$ADMIN_SENHA" \
        web python manage.py createsuperuser --noinput \
        || aviso "O administrador não foi criado (talvez já exista). Crie depois com: docker compose exec web python manage.py createsuperuser"
fi

# ---------------------------------------------------------------- HTTPS e Nginx

if ! sudo test -f "$CERTIFICADO" && [ -n "${CLOUDFLARE_TOKEN:-}" ]; then
    passo "Emitindo o certificado HTTPS pelo DNS da Cloudflare"
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-dns-cloudflare
    sudo install -d -m 700 /etc/letsencrypt
    printf 'dns_cloudflare_api_token = %s\n' "$CLOUDFLARE_TOKEN" | sudo tee /etc/letsencrypt/cloudflare.ini > /dev/null
    sudo chmod 600 /etc/letsencrypt/cloudflare.ini
    sudo certbot certonly --non-interactive --agree-tos -m "$EMAIL_CERTIFICADO" \
        --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
        --dns-cloudflare-propagation-seconds 30 \
        --deploy-hook "systemctl reload nginx" \
        -d "$DOMINIO" \
        || aviso "O certificado não foi emitido. Confira o token da Cloudflare; o sistema segue só com HTTP."
fi

passo "Configurando o Nginx"
PROXY='
    # Fotos do ponto e do perfil (a aplicação aceita até 5 MB por foto de perfil).
    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }'
if sudo test -f "$CERTIFICADO"; then
    HTTPS=1
    sudo tee /etc/nginx/sites-available/registro-ponto > /dev/null <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 301 https://$DOMINIO\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMINIO;

    ssl_certificate /etc/letsencrypt/live/$DOMINIO/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMINIO/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
$PROXY
}
EOF
else
    HTTPS=0
    sudo tee /etc/nginx/sites-available/registro-ponto > /dev/null <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
$PROXY
}
EOF
fi
sudo ln -sf /etc/nginx/sites-available/registro-ponto /etc/nginx/sites-enabled/registro-ponto
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

# ---------------------------------------------------------------- backup e rotinas

passo "Configurando o backup diário (02h30, guarda 14 dias)"
# Backups têm dados pessoais e biometria: só o dono lê.
sudo install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$BACKUPS"
sudo chmod 700 "$BACKUPS"
sudo tee /usr/local/bin/backup-registro-ponto > /dev/null <<'EOF'
#!/bin/sh
# Backup do banco e das fotos do Registro de Ponto; mantém os últimos 14 dias.
set -eu
umask 077
cd /opt/registro-ponto
set -a; . ./.env; set +a
DESTINO=/var/backups/registro-ponto
DATA=$(date +%Y-%m-%d_%H%M)

docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom > "$DESTINO/banco-$DATA.dump"
docker run --rm --user "$(id -u):$(id -g)" -v registro-ponto_media_data:/dados:ro -v "$DESTINO":/destino alpine \
  sh -c "umask 077 && tar czf /destino/media-$DATA.tar.gz -C /dados ."

find "$DESTINO" -type f -mtime +14 ! -name backup.log -delete
EOF
sudo chmod 755 /usr/local/bin/backup-registro-ponto

ROTINAS=$(crontab -l 2>/dev/null || true)
if ! grep -q backup-registro-ponto <<< "$ROTINAS"; then
    ROTINAS+=$'\n'"30 2 * * * /usr/local/bin/backup-registro-ponto >> $BACKUPS/backup.log 2>&1"
fi
if ! grep -q sincronizar_feriados <<< "$ROTINAS"; then
    ROTINAS+=$'\n'"0 6 1 1 * cd $PASTA && docker compose exec -T web python manage.py sincronizar_feriados --ano \$(date +\\%Y)"
fi
sed '/^$/d' <<< "$ROTINAS" | crontab -

echo "Primeiro backup de teste..."
sg docker -c /usr/local/bin/backup-registro-ponto \
    && ls -lh "$BACKUPS" \
    || aviso "O backup de teste falhou. Rode depois: backup-registro-ponto"

# ---------------------------------------------------------------- resumo

passo "Instalação concluída"
if [ "$HTTPS" = 1 ]; then
    ENDERECO="https://$DOMINIO/"
else
    ENDERECO="http://$DOMINIO/ (ou http://$IP_SERVIDOR/)"
    aviso "Instalado só com HTTP: a câmera não funciona fora do próprio servidor."
    echo "Para ativar o HTTPS, rode o script de novo e informe o token da Cloudflare."
fi
cat <<EOF

  Endereço:        $ENDERECO
  Pasta:           $PASTA
  Configuração:    $PASTA/.env
  Backups:         $BACKUPS (todo dia às 02h30)
  Logs:            cd $PASTA && docker compose logs -f web

  Na Cloudflare, crie o registro DNS:
    Tipo A   Nome: $DOMINIO   Conteúdo: $IP_SERVIDOR   Proxy: desligado (DNS only, nuvem cinza)

  Para atualizar o sistema depois: bash $PASTA/scripts/instalar.sh
  Saia e entre de novo no SSH para usar o docker sem sudo.
EOF
exit 0
}
