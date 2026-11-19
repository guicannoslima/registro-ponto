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
**Colaborador**. A view de cadastro completa o perfil criado. A migração `0006` cria o
perfil de quem já existia sem ele. **Consequência:** o passo manual de criar o perfil
do administrador saiu da documentação.

## `.idea/` fora do Git — 18/11/2026

As configurações do PyCharm guardam caminhos e o nome do interpretador de cada
máquina, e nem todos usam o PyCharm. A pasta inteira é ignorada; a configuração
recomendada está em [Desenvolvimento](DESENVOLVIMENTO.md#pycharm).

## Conteúdo interno com CSS próprio — 18/11/2026

**Problema:** o redesenho aprovado muda todo o conteúdo interno, mas o header e o login
devem ficar como estão. **Escolha:** um `interno.css` separado, com todas as regras sob
`.principal-interno` e carregado só por `base_interna.html`; o `estilo.css` não muda.
A Figtree é servida localmente, como no Prime Central. **Consequência:** o azul da ação
passa a `#0A6EA3` (5,57:1 com branco) só no conteúdo; o header mantém o `#03A9F5`.

## Constantes em `constants.py` — 18/11/2026

Jornada, tolerância, intervalo mínimo, períodos das telas e textos fixos estavam repetidos
em `views.py`, `relatorios.py`, `forms.py` e `apresentacao.py`. Ficam agora em
`ponto/constants.py`, e os módulos importam de lá.

## Como registrar uma nova decisão

Crie uma seção de nível 2 com o título da decisão e a data. Descreva o problema, as
alternativas consideradas, a escolha e a consequência. Ao substituir uma decisão,
mantenha a antiga e aponte para a nova.

## Menu com subitens e administração — 18/11/2026

**Decisão implementada por pedido explícito do usuário:** revisar o cabeçalho anteriormente
congelado, abrir submenus por clique e aproveitar toda a largura em 1333 px. A nova página
**Administração e navegação** no Figcraft precedeu a implementação. O CSS fica no arquivo
interno, com cabeçalho sob `.topo-aplicacao`; `estilo.css` e as telas públicas não mudam.

O administrador passa a cadastrar e editar usuários dentro do sistema e configurar o SMTP.
Credenciais SMTP ficam cifradas no banco e nunca voltam para o campo da tela; a configuração
do ambiente vale até o primeiro salvamento. Teste de envio requer uma ação própria na tela.
Formulários e views ficam concentrados em `forms.py` e `views.py`, e as exceções de domínio
em `exceptions.py`, conforme orientação posterior do usuário.

## Serviços, e-mail, testes e nomenclatura — 18/11/2026

**Decisão implementada por pedido do usuário:** os serviços de apresentação, sequência e
registro de batidas ficam em `ponto/services.py`; o módulo de envio chama-se `ponto/email.py`;
todos os testes ficam em `ponto/tests.py`. Formulários, views e exceções continuam nos arquivos
únicos definidos anteriormente. Os imports e a referência do backend nos settings foram atualizados.

O papel passa a ser exibido como **Colaborador**, inclusive nos formulários e no admin Django.
A migração `0009` altera somente rótulos e metadados; preserva os identificadores e valores
já gravados no banco. Não muda regras de jornada, permissões ou sequência de batidas.
Os campos e botões comuns têm 48 px para alinhar as ações dos formulários, como no exemplo
`IM04.png` fornecido pelo usuário; ações compactas das tabelas mantêm seu tamanho próprio.
