# Decisões de implementação

Esta página registra por que os caminhos atuais foram escolhidos. Propostas
futuras permanecem separadas dos mecanismos existentes.

## Docker com Gunicorn, WhiteNoise e PostgreSQL — 11/11/2026

**Problema:** rodar o projeto exigia instalar Python e PostgreSQL na máquina.
**Escolha:** `compose.yaml` com a aplicação e um `postgres:17-alpine`; Gunicorn como
servidor e WhiteNoise para os estáticos, sem um Nginx separado.
**Consequência:** `docker compose up` sobe o ambiente completo. O entrypoint aplica
migrações e `collectstatic` a cada subida ([Implantação](IMPLANTACAO.md)).

## Requirements por ambiente — 18/11/2026

As dependências ficam em `requirements/base.txt`, `development.txt` e `production.txt`,
como no `dsync-specshop`. O Gunicorn entra só na imagem; o Ruff, só no ambiente local.
A imagem Docker instala apenas `production.txt`.

## Ruff com 120 colunas — 18/11/2026

O lint e a formatação seguem o padrão do `dsync-specshop`: Ruff configurado no
`pyproject.toml`, linhas de até 120 colunas e aspas simples. Os `models.py` ficam fora
do formatador para preservar o alinhamento manual. O código anterior ainda não foi
adequado ([Roadmap](ROADMAP.md)).

## Django 5.2 LTS — 18/11/2026

**Problema:** o projeto usava Django 6.1.1, versão sem suporte estendido.
**Alternativas:** (a) seguir na série 6.x; (b) fixar a LTS 5.2, com suporte até
abril de 2028. **Escolha:** (b), com `Django~=5.2.19` para receber só correções.
**Consequência:** duas adaptações. O `MAILERS`, exclusivo do 6.1, virou as variáveis
`EMAIL_*`; sem isso, o 5.2 ignoraria a configuração e o e-mail pararia sem erro.
`DEFAULT_AUTO_FIELD = BigAutoField` mantém as chaves das migrações geradas no 6.x,
cujo padrão já era `BigAutoField`.

## Perfil criado por signal — 18/11/2026

**Problema:** o `Perfil` só era criado na tela de cadastro. Usuários do
`createsuperuser`, do admin ou do shell ficavam sem perfil, e todas as telas quebravam
com `RelatedObjectDoesNotExist`. **Alternativas:** (a) tratar a ausência em cada
view; (b) criar o perfil sempre que um `User` nasce. **Escolha:** (b), com um signal
`post_save` em `ponto/signals.py`: superusuário vira **Administrador** e os demais,
**Funcionário**. A view de cadastro completa o perfil criado. A migração `0006` cria o
perfil de quem já existia sem ele. **Consequência:** o passo manual de criar o perfil
do administrador saiu da documentação.

## `.idea/` fora do Git — 18/11/2026

As configurações do PyCharm guardam caminhos e o nome do interpretador de cada
máquina, e nem todos usam o PyCharm. A pasta inteira é ignorada; a configuração
recomendada está em [Desenvolvimento](DESENVOLVIMENTO.md#pycharm).

## Como registrar uma nova decisão

Crie uma seção de nível 2 com o título da decisão e a data. Descreva o problema, as
alternativas consideradas, a escolha e a consequência. Ao substituir uma decisão,
mantenha a antiga e aponte para a nova.
