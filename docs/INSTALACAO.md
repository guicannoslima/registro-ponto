# Instalação no servidor

O script `scripts/instalar.sh` instala o Registro de Ponto num Ubuntu Server 24.04 LTS de uma vez:
Docker, projeto, Nginx com HTTPS, administrador e backup diário. O servidor fica na rede
interna, com o domínio apontado para o IP interno pela Cloudflare. A aplicação e o PostgreSQL
rodam em Docker, e o Nginx recebe as conexões com certificado do Let's Encrypt.

Nos exemplos, troque `ponto.exemplo.com.br` pelo domínio real. A aplicação é administrada pelo
usuário padrão do servidor, `prime`, com acesso por senha; o `root` só entra se faltar `sudo`. Linhas
iniciadas por `#` dentro dos blocos são comentários.

## Instalação automática

### O que preparar antes

1. **Token do GitHub.** O GitHub não aceita a senha da conta para clonar. Em
   **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token**, escolha o repositório `primecartorios/registro-ponto` e a permissão
   **Contents: Read-only**. Copie o token gerado, que começa com `github_pat_`.
2. **Token da API da Cloudflare**, para o certificado HTTPS. Em **Cloudflare → My Profile →
   API Tokens → Create Token**, use o modelo **Edit zone DNS** e escolha a zona do domínio.
   Como o servidor tem IP interno, o Let's Encrypt não consegue acessá-lo; o certificado é
   validado por um registro DNS temporário que o script cria com esse token.
3. **Registro DNS na Cloudflare:** tipo `A`, nome `ponto` (ou o subdomínio escolhido), conteúdo
   o IP interno do servidor e **Proxy status: DNS only** (nuvem cinza). Com o proxy ligado, a
   Cloudflare tentaria alcançar o IP interno pela internet e o acesso falharia.
4. **Conta Gmail** com [senha de app](https://support.google.com/accounts/answer/185833), para os
   e-mails de redefinição de senha.

O HTTPS é obrigatório: o navegador só libera a câmera do registro facial em páginas seguras.
Sem o token da Cloudflare, o script instala só com HTTP e a câmera não funciona.

### Rodar o script

Entre no servidor com o usuário `prime` e a senha dele, baixe o script com o token do GitHub
e rode:

```bash
ssh prime@IP_DO_SERVIDOR
curl -fsSL -H "Authorization: Bearer TOKEN_DO_GITHUB" \
  https://raw.githubusercontent.com/primecartorios/registro-ponto/main/scripts/instalar.sh -o instalar.sh
bash instalar.sh
```

O script pede, nesta ordem: domínio, IP interno (sugere o detectado), usuário e token do
GitHub, conta e senha de app do Gmail, usuário, e-mail e senha do administrador, token da
Cloudflare e e-mail para avisos do certificado. Depois disso não há mais perguntas, só a senha
do `sudo` no início. A primeira instalação leva de 5 a 15 minutos.

No fim, ele mostra o endereço de acesso e o registro DNS a conferir na Cloudflare. Entre com
o administrador e siga o [primeiro acesso](#10-primeiro-acesso).

### O que o script faz

| Etapa | Detalhe |
| --- | --- |
| Sistema | Atualiza os pacotes, ajusta o fuso para `America/Sao_Paulo`, instala Git, Nginx e `ufw` |
| Firewall | Libera só SSH, HTTP e HTTPS |
| Docker | Instala pelo repositório oficial e coloca o `prime` no grupo `docker` |
| Projeto | Clona em `/opt/registro-ponto` por HTTPS com `usuário:token` |
| `.env` | Gera `SECRET_KEY` e senha do banco; grava domínio, IP e e-mail |
| Porta 8000 | Restrita ao próprio servidor (`compose.override.yaml`); o acesso passa pelo Nginx |
| Aplicação | Constrói e sobe os containers, espera responder e cria o administrador |
| HTTPS | Emite o certificado pelo DNS da Cloudflare; a renovação é automática |
| Backup | Banco e fotos todo dia às 02h30 em `/var/backups/registro-ponto`, por 14 dias |
| Feriados | Sincroniza os feriados nacionais em 1º de janeiro |

O token do GitHub fica na URL do repositório (`/opt/registro-ponto/.git/config`, legível só
pelo `prime`), para as atualizações. O token da Cloudflare fica em
`/etc/letsencrypt/cloudflare.ini`, legível só pelo `root`. Se um token for revogado, gere outro
e troque o valor nesses arquivos.

### Atualizar

Rode o script de novo. Ele baixa o código novo, reconstrói os containers e aplica as migrações,
sem trocar senhas, chave ou dados, e não repete as perguntas já respondidas:

```bash
cd /opt/registro-ponto
backup-registro-ponto
bash scripts/instalar.sh
```

## Instalação manual

Os passos abaixo fazem o mesmo que o script, um comando de cada vez. Use-os como referência
ou para instalar em um cenário diferente.

## 1. Antes de começar

| Item | Recomendação |
| --- | --- |
| Servidor | Ubuntu Server 24.04 LTS, 4 vCPU e 4 GB de RAM ([capacidade](CARGA_50_COLABORADORES.md#configuração-indicada)) |
| Disco | 20 GB livres para sistema, imagens Docker, banco e fotos |
| Domínio | Registro DNS do tipo `A` na Cloudflare apontando para o IP interno, com proxy desligado |
| Portas | 22 (SSH), 80 e 443 (HTTP e HTTPS) acessíveis na rede interna |
| Repositório | Acesso de leitura a `github.com/primecartorios/registro-ponto` |
| E-mail | Conta Gmail com [senha de app](https://support.google.com/accounts/answer/185833), para a redefinição de senha |

Para conferir o DNS, rode `dig +short ponto.exemplo.com.br` numa máquina da rede: a resposta
deve ser o IP interno do servidor.

## 2. Preparar o sistema

O acesso ao servidor é por usuário e senha, sem chave SSH. Entre com o usuário `prime`;
o SSH pede a senha dele:

```bash
ssh prime@IP_DO_SERVIDOR
```

Confira se o `prime` pode usar `sudo`. O comando pede a senha do `prime`:

```bash
sudo -v && echo "sudo liberado"
```

Se aparecer `prime is not in the sudoers file`, libere pelo `root`. O `su -` pede a senha
do `root`; depois, saia do servidor e entre de novo como `prime` para a permissão valer:

```bash
su -
usermod -aG sudo prime
exit
exit
```

Atualize o sistema e ajuste o fuso horário:

```bash
sudo apt update && sudo apt upgrade -y
sudo timedatectl set-timezone America/Sao_Paulo
sudo apt install -y git curl ca-certificates unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades   # responda "Sim" para atualizações automáticas de segurança
```

Ative o firewall liberando somente o SSH por enquanto. Libere o SSH antes do `enable`, para
não perder o acesso:

```bash
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```

Daqui em diante, todos os comandos são executados pelo `prime`, com `sudo` quando indicado.
Com acesso por senha, use senhas longas para o `prime` e o `root`: o SSH fica exposto na internet.

## 3. Instalar o Docker

Instale o Docker Engine e o plugin Compose pelo repositório oficial, conforme a
[documentação do Docker para Ubuntu](https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Permita que o usuário `prime` use o Docker sem `sudo` e confira a instalação:

```bash
sudo usermod -aG docker prime
newgrp docker
docker run --rm hello-world
docker compose version          # precisa ser 2.24 ou mais recente (usado no passo 6)
sudo systemctl enable docker containerd
```

## 4. Baixar o código

O repositório é privado, e o GitHub não aceita usuário e senha para clonar. Por isso o
servidor usa uma chave de implantação (deploy key) própria, que dá só leitura a este
repositório e não muda o acesso ao servidor, que continua por senha:

```bash
ssh-keygen -t ed25519 -C "registro-ponto@$(hostname)" -f ~/.ssh/registro_ponto -N ""
cat ~/.ssh/registro_ponto.pub
```

No GitHub, abra o repositório em **Settings → Deploy keys → Add deploy key**, cole a chave
pública exibida, dê um nome como `servidor-producao` e deixe **Allow write access**
desmarcado. Depois configure o SSH para usar essa chave e clone o projeto em `/opt`:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-registro-ponto
    HostName github.com
    User git
    IdentityFile ~/.ssh/registro_ponto
    IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config

sudo mkdir -p /opt/registro-ponto
sudo chown prime:prime /opt/registro-ponto
git clone git@github-registro-ponto:primecartorios/registro-ponto.git /opt/registro-ponto
cd /opt/registro-ponto
```

Na primeira conexão, confirme a impressão digital do GitHub com `yes`. Mantenha a pasta
`/opt/registro-ponto`: o nome dela define o prefixo dos volumes Docker (`registro-ponto_`),
usado nos backups.

## 5. Configurar o `.env`

Gere a chave do Django e a senha do banco. Os valores usam só letras, números, `-` e `_`,
porque o Docker Compose interpreta o caractere `$`:

```bash
gerar() { python3 -c "import secrets, string; a = string.ascii_letters + string.digits + '-_'; print(''.join(secrets.choice(a) for _ in range($1)))"; }
echo "SECRET_KEY=$(gerar 64)"
echo "DB_PASSWORD=$(gerar 32)"
```

Copie o modelo e edite com os valores gerados:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

O arquivo deve ficar assim, com os seus valores:

```ini
SECRET_KEY=valor-gerado-com-64-caracteres
DEBUG=False
ALLOWED_HOSTS=ponto.exemplo.com.br
CSRF_TRUSTED_ORIGINS=https://ponto.exemplo.com.br

DB_NAME=registro_ponto
DB_USER=registro_ponto
DB_PASSWORD=valor-gerado-com-32-caracteres
DB_HOST=localhost
DB_PORT=5432

EMAIL_HOST_USER=conta@gmail.com
EMAIL_HOST_PASSWORD=senha-de-app-do-google
```

- `DEBUG` precisa ser `False` em produção.
- `ALLOWED_HOSTS` recebe só o domínio, sem `https://`. Para mais de um endereço, separe por vírgula.
- `CSRF_TRUSTED_ORIGINS` recebe o endereço completo com `https://`. Sem ele, os formulários
  respondem **403** depois que o HTTPS estiver ativo.
- `DB_HOST` e `DB_PORT` podem ficar como estão: o `compose.yaml` aponta a aplicação para o
  container do banco.
- `DB_NAME`, `DB_USER` e `DB_PASSWORD` criam o banco na primeira subida. Depois disso, mudar
  esses valores no `.env` não altera o banco existente.
- `EMAIL_HOST_USER` e `EMAIL_HOST_PASSWORD` são obrigatórios. Sem eles a aplicação não inicia.
  O administrador pode trocar a conta depois em **Administração → Envio de e-mails**.

O significado de cada variável está em [Implantação](IMPLANTACAO.md#variáveis-de-ambiente).

## 6. Restringir a porta da aplicação

O `compose.yaml` publica a porta 8000 em todas as interfaces, e o Docker ignora as regras
do `ufw`. Para que só o Nginx do próprio servidor alcance a aplicação, crie um
`compose.override.yaml` local, que o Compose carrega automaticamente:

```bash
cat > compose.override.yaml <<'EOF'
services:
  web:
    ports: !override
      - "127.0.0.1:8000:8000"
EOF
echo "compose.override.yaml" >> .git/info/exclude
docker compose config | grep -A6 "ports:"
```

A saída deve mostrar `host_ip: 127.0.0.1`. A linha do `.git/info/exclude` impede que o
arquivo apareça como alteração no Git deste servidor.

## 7. Subir a aplicação

```bash
docker compose up -d --build
```

A primeira subida leva alguns minutos. O build compila as dependências e baixa cerca de
39 MB de modelos de reconhecimento facial do GitHub, conferindo o SHA-256 de cada arquivo.
Ao iniciar, o container aplica as migrações, carrega os feriados nacionais do ano corrente
e coleta os arquivos estáticos.

Confira se os dois containers estão de pé e se a aplicação responde:

```bash
docker compose ps                         # db como "healthy" e web como "Up"
docker compose logs --tail=50 web         # deve terminar com "Booting worker" do Gunicorn
curl -sI http://127.0.0.1:8000/login/ -H "Host: ponto.exemplo.com.br" | head -1
```

O `curl` deve responder `HTTP/1.1 200 OK`. Um `400` indica que o domínio não está em
`ALLOWED_HOSTS`.

## 8. Criar o administrador

```bash
docker compose exec web python manage.py createsuperuser
```

Informe nome de usuário, e-mail e senha. O superusuário entra no sistema com o papel
**Administrador**.

## 9. Publicar com Nginx e HTTPS

Instale o Nginx e libere HTTP e HTTPS no firewall:

```bash
sudo apt install -y nginx
sudo ufw allow 'Nginx Full'
```

Crie o site, trocando o domínio:

```bash
sudo tee /etc/nginx/sites-available/registro-ponto > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name ponto.exemplo.com.br;

    # Fotos do ponto e do perfil (a aplicação aceita até 5 MB por foto de perfil).
    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
EOF
sudo ln -s /etc/nginx/sites-available/registro-ponto /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Com IP interno, o Let's Encrypt não alcança o servidor. Emita o certificado pelo DNS da
Cloudflare, com o token descrito na [instalação automática](#o-que-preparar-antes) e o
[plugin oficial do Certbot](https://certbot-dns-cloudflare.readthedocs.io/):

```bash
sudo apt install -y certbot python3-certbot-dns-cloudflare python3-certbot-nginx
echo "dns_cloudflare_api_token = TOKEN_DA_CLOUDFLARE" | sudo tee /etc/letsencrypt/cloudflare.ini > /dev/null
sudo chmod 600 /etc/letsencrypt/cloudflare.ini
sudo certbot certonly --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  --dns-cloudflare-propagation-seconds 30 --deploy-hook "systemctl reload nginx" -d ponto.exemplo.com.br
sudo certbot install --nginx --cert-name ponto.exemplo.com.br --redirect
sudo certbot renew --dry-run
```

O `certonly` pede um e-mail para avisos de vencimento. O `install` coloca o certificado no
site do Nginx e redireciona o HTTP para o HTTPS. A renovação fica agendada no `certbot.timer`;
o `--dry-run` confirma que ela funciona.

## 10. Primeiro acesso

Abra `https://ponto.exemplo.com.br/` e entre com o administrador do passo 8. Em seguida:

1. **Administração → Envio de e-mails:** envie um e-mail de teste para confirmar o SMTP.
2. **Administração → Jornadas:** revise os oito modelos de exemplo e ajuste os da empresa.
3. **Administração → Feriados:** confira o ano corrente e cadastre os feriados estaduais,
   municipais e datas próprias da empresa.
4. **Administração → Usuários:** cadastre gestores e colaboradores, com papel, gestor e jornada.
5. **Gestão → Cadastros faciais:** cadastre o rosto de quem vai registrar o ponto pela câmera.

O uso de cada tela está no [manual de uso](USO.md).

## 11. Backup diário

O backup precisa de duas partes: o banco PostgreSQL e o volume `registro-ponto_media_data`,
que guarda as fotos de perfil. Crie o script:

```bash
sudo install -d -m 700 -o prime -g prime /var/backups/registro-ponto

sudo tee /usr/local/bin/backup-registro-ponto > /dev/null <<'EOF'
#!/bin/sh
# Backup do banco e das fotos do Registro de Ponto; mantém os últimos 14 dias.
set -eu
umask 077
cd /opt/registro-ponto
set -a; . ./.env; set +a
DESTINO=/var/backups/registro-ponto
DATA=$(date +%Y-%m-%d_%H%M)

docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom \
  > "$DESTINO/banco-$DATA.dump"
docker run --rm --user "$(id -u):$(id -g)" -v registro-ponto_media_data:/dados:ro -v "$DESTINO":/destino alpine \
  sh -c "umask 077 && tar czf /destino/media-$DATA.tar.gz -C /dados ."

find "$DESTINO" -type f -mtime +14 -delete
EOF
sudo chmod 755 /usr/local/bin/backup-registro-ponto
backup-registro-ponto && ls -lh /var/backups/registro-ponto
```

Agende para todo dia às 02h30:

```bash
(crontab -l 2>/dev/null; echo "30 2 * * * /usr/local/bin/backup-registro-ponto >> /var/backups/registro-ponto/backup.log 2>&1") | crontab -
crontab -l
```

Os arquivos ficam no mesmo servidor. Copie-os regularmente para outro local, como um
armazenamento de objetos do provedor ou outra máquina, para não perder os dados junto
com o servidor. Os backups contêm dados pessoais e biometria: restrinja o acesso a eles.

### Restaurar um backup

Faça a restauração primeiro num servidor de teste. Ela substitui o banco atual:

```bash
cd /opt/registro-ponto
set -a; . ./.env; set +a
docker compose stop web
docker compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists \
  < /var/backups/registro-ponto/banco-AAAA-MM-DD_HHMM.dump
docker run --rm -v registro-ponto_media_data:/dados -v /var/backups/registro-ponto:/origem alpine \
  sh -c "rm -rf /dados/* && tar xzf /origem/media-AAAA-MM-DD_HHMM.tar.gz -C /dados"
docker compose start web
```

## 12. Atualizar para uma nova versão

```bash
cd /opt/registro-ponto
backup-registro-ponto
git pull
docker compose up -d --build
docker compose logs --tail=50 web
docker image prune -f
```

O container aplica as migrações novas ao subir. Se algo falhar, volte ao commit anterior
com `git checkout COMMIT_ANTERIOR` e rode `docker compose up -d --build`. Se a versão nova
já tiver migrado o banco, restaure também o backup feito antes da atualização.

## 13. Feriados de cada ano

Toda subida do container carrega os feriados nacionais do ano corrente sem duplicar datas.
Para não depender de um reinício na virada do ano, agende a sincronização para 1º de janeiro:

```bash
(crontab -l; echo '0 6 1 1 * cd /opt/registro-ponto && docker compose exec -T web python manage.py sincronizar_feriados --ano $(date +\%Y)') | crontab -
```

Os feriados estaduais e municipais continuam sendo cadastrados em **Administração → Feriados**.

## Comandos de operação

| Ação | Comando, na pasta `/opt/registro-ponto` |
| --- | --- |
| Ver o status | `docker compose ps` |
| Acompanhar os logs | `docker compose logs -f web` |
| Reiniciar a aplicação | `docker compose restart web` |
| Parar tudo | `docker compose down` |
| Subir novamente | `docker compose up -d` |
| Shell do Django | `docker compose exec web python manage.py shell` |
| Shell do banco | `docker compose exec db psql -U registro_ponto -d registro_ponto` |
| Logs do Nginx | `sudo tail -f /var/log/nginx/error.log` |

**`docker compose down -v` apaga os volumes, com o banco e as fotos.** Não use esse comando
em produção.

## Problemas comuns

| Sintoma | Causa provável e solução |
| --- | --- |
| **400 Bad Request** | Domínio fora de `ALLOWED_HOSTS`. Corrija o `.env` e rode `docker compose up -d`. |
| **403** ao enviar formulários | `CSRF_TRUSTED_ORIGINS` sem o endereço exato com `https://`. Corrija e rode `docker compose up -d`. |
| **502 Bad Gateway** | A aplicação não está de pé. Veja `docker compose ps` e `docker compose logs web`. |
| Container `web` reiniciando | Variável obrigatória ausente no `.env`, como `EMAIL_HOST_USER`, ou banco indisponível. Veja os logs. |
| Senha do banco recusada | O `DB_PASSWORD` mudou depois da primeira subida. Volte ao valor original ou altere a senha dentro do PostgreSQL. |
| Câmera não abre | A página não está em HTTPS ou o navegador bloqueou a permissão. Acesse pelo domínio com `https://`. |
| Build falha ao baixar modelos faciais | O servidor não alcança o GitHub por HTTPS. Libere a saída na porta 443 e repita o build. |
| E-mail de redefinição não chega | Senha de app inválida ou verificação em duas etapas desativada na conta Google. Teste em **Administração → Envio de e-mails**. |
| Domínio não abre, mas o IP abre | Registro na Cloudflare com proxy ligado (nuvem laranja). Mude para **DNS only**. |
| Certificado não emitido | Token da Cloudflare sem permissão de editar o DNS da zona. Gere outro e rode `bash /opt/registro-ponto/scripts/instalar.sh` de novo. |
| Valor do `.env` cortado | O valor tem `$`. Gere outro só com letras, números, `-` e `_`. |

Em 19/11/2026, a instalação e a reexecução foram verificadas num Ubuntu 24.04 em Docker,
com systemd, daemon Docker próprio e credenciais fictícias. O teste cobriu login, Nginx,
backup com restauração, preservação de senhas e HTTPS com certificado local. O instalador
passou a iniciar o Nginx antes de recarregá-lo. Consulte o
[procedimento, os resultados e os limites](TESTES.md#instalação-em-ubuntu-2404-no-docker--19112026).
Ainda falta validar numa VM completa e emitir/renovar o certificado real pela Cloudflare.
