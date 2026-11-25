# Ponto de retomada

Estado em 25/11/2026, revisão `844b0b7` publicada em `origin/main`. Esta página diz o que já
foi feito, o que está pendente e como continuar o trabalho sem repetir o que já se decidiu.
O que entrou de 23 a 25/11 está em [Revisão de 23 a 25/11](#revisão-de-23-a-2511--planilha-banco-de-horas-e-ajustes);
o texto logo abaixo é o histórico até 19/11.

Revisão local posterior, sem push: reconhecimento facial pessoal e terminal compartilhado
implementados; dependências e modelos instalados, migração `0007` aplicada no banco local.
O registro reconhece e bate o ponto automaticamente; a câmera abre ao entrar nas telas.
O nome da conta local `admin` foi atualizado para **Caio** a pedido do usuário.
Administração de usuários e SMTP implementada; migração `0008` aplicada no banco local.
O menu foi reorganizado por clique, e o cabeçalho e conteúdo agora usam toda a largura,
por autorização explícita do usuário. Formulários em `forms.py`, views em `views.py` e
exceções em `exceptions.py`. As telas públicas continuam como estavam.
Serviços de apresentação, batidas e sequência reunidos em `services.py`; módulo de e-mail
renomeado para `email.py`, e os testes reunidos em `tests.py`. A interface usa
**Colaborador**, e botões comuns e campos têm 48 px para alinhar formulários.
A migração `0009`, somente de rótulos, foi aplicada no banco local.
`services.py` reúne regras, consultas e preparação de dados, incluindo `_gestor` e `_pessoas`.
Formatadores de datas e durações e os auxiliares HTTP `_limitar_captura` e `_erro` ficam em `utils.py`.
O registro pessoal e do terminal utiliza `registrar_ponto_facial` em `services.py`, sem
dependência de requisição, sessão ou resposta HTTP. As views usam os adaptadores de `utils.py`.
A tela Cadastrar rosto consulta o cadastro da pessoa selecionada e diferencia cadastrar,
substituir e remover. A remoção só aparece quando existe cadastro facial.
Meu ponto → Meu perfil permite escolher ou remover a foto da confirmação. Ao registrar,
foto ou imagem genérica com nome aparecem por 3 segundos, com **PONTO REGISTRADO - PRIMEIRO NOME**.
Os atalhos de cadastro facial e terminal saíram do início. Cadastro fica em Gestão;
terminal, em Administração, disponível também aos gestores. Meu perfil é o último item
de Meu ponto; Cadastrar usuário aparece somente na tela Usuários.
A migração `0010` da foto de perfil foi aplicada no banco local.
Fotos novas são convertidas para WebP de 512 × 512; `media/.gitkeep` é versionado, fotos não.
Remoção e substituição facial usam confirmDialog. O cadastro facial tem faixa de estado
em toda a largura do cartão; busca de usuários alinhada; CPF com máscara; exclusão de
batida ocupa a largura do layout. O build Docker inclui os dois modelos públicos de IA,
verificados por SHA-256, sem versionar os binários. Relatórios usam a consulta de escopo
de `services.py`: administrador vê todos; gestor, subordinados; colaborador, apenas a si.
Em 19/11, o aviso de rosto sem cadastro passou a ocupar uma faixa destacada no topo;
a confirmação de cadastro facial usa o cartão verde por 3 segundos. Fotos acima de
16 milhões de pixels são reduzidas automaticamente para WebP de 512 × 512.
O aviso de intervalo na câmera pessoal ocupa uma camada levemente transparente no
rodapé da prévia por 6 segundos, sem repetir capturas durante a exibição.
Os demais avisos operacionais da câmera também ficam nessa camada inferior, sem texto
separado entre a prévia e os botões.
A câmera também pode ser ativada por clique/toque em toda a prévia, além do botão
Retomar câmera; a área aceita teclado e bloqueia aberturas simultâneas.
O terminal compartilhado renova a sessão enquanto aberto/conectado, incluindo durante
a pausa da câmera. Webcam desliga após 30 segundos sem interação ou nova batida;
retomada por toque/botão. Respostas repetidas não reiniciam o prazo.
Sem painel lateral; Encerrar terminal fica no cabeçalho.
O terminal também não tem título ou introdução: câmera e controles se ajustam à altura
disponível, sem rolagem em computador, tablet e celular, inclusive em paisagem.
As prévias pessoal, de cadastro e de terminal têm guia central de quatro cantos em
cinza claro semitransparente, com centro livre, visível apenas com a câmera ativa.
O gestor precisa cadastrar os rostos reais antes do uso. Não há prova de vida
([uso e limitações](USO.md#registro-por-reconhecimento-facial)).

## Onde o projeto está

| Área | Estado |
| --- | --- |
| Ambiente | `venv` do PyCharm (Python 3.13), Django 5.2 LTS, PostgreSQL local; Docker Desktop local na porta 8000 ([Implantação](IMPLANTACAO.md)) |
| Produção | `srv-ponto`, https://ponto.primecartorios.com.br, HTTPS com renovação automática; câmera testada pelo usuário em 25/11 |
| Telas internas | Redesenhadas a partir da proposta aprovada no Figcraft ([design](../design/README.md)) |
| Página inicial | Abas **Hoje**, **Ontem** e **Sua equipe** (gestor), anel da jornada e linha do dia |
| Relatório | **Gerar relatório** mostra o cartão ponto em PDF num iframe; **Baixar PDF** baixa o arquivo |
| PDF | Cartão ponto no modelo de mercado, uma página por pessoa ([Uso](USO.md#relatório-de-banco-de-horas)) |
| Perfil | Todo usuário ganha perfil por signal ([decisão](DECISOES.md#perfil-criado-por-signal--18112026)) |
| Testes | 136 testes em `ponto/tests.py`; em 25/11, 135 aprovados no container e só a falha conhecida da foto de perfil ([Testes](TESTES.md)) |
| Folgas e banco de horas | Gestão › Folgas, banco de horas desde a primeira batida com adicional de domingo, tela por mês de origem e saldo no cartão ponto ([Uso](USO.md#folgas-e-banco-de-horas)) |
| Planilha retroativa | Importação de `.xlsx` de banco de horas; o administrador acha o colaborador pelo CPF e o gestor escolhe o colaborador |
| Instalação | Instalação e reexecução verificadas em Ubuntu 24.04 no Docker; falta VM completa e certificado real ([teste](TESTES.md#instalação-em-ubuntu-2404-no-docker--19112026)) |
| Administração | Menu com Usuários e Envio de e-mails; cadastro/edição de contas, vínculo de equipe e SMTP |
| Reconhecimento facial | Verificação da pessoa logada, cadastro supervisionado e terminal restrito à equipe; pranchas na página **Câmera** do Figcraft |
| Capacidade | Indicação de 4 vCPU / 4 GB para pico de 50 pessoas; 1.200 POSTs sem falhas, imagem e recursos de teste descartados ([Carga de 50](CARGA_50_COLABORADORES.md)) |

## Decisões pendentes do usuário

1. **Banco de horas:** adicional de domingo e tela por mês de origem já entraram (23/11). Sem
   adicional de 50%/100% em dia útil, validade das horas, fechamento por período e extrato do
   colaborador. Em 25/11 o usuário disse que configura **depois**; não puxar o assunto antes.
2. **Atalho para dias incompletos:** a lista com **Pedir ajuste** e **Lançar ponto** acima do
   iframe do relatório não é necessária agora (resposta de 25/11).

**Decidido em 25/11/2026 — café:** o café **conta como hora trabalhada**. As batidas de saída
e volta do café só registram que ele foi feito e não entram na conta. A carga de **7h45**
(`JORNADA_DIARIA`) está certa; o `HORARIO_DE_TRABALHO` impresso no cartão continua mostrando
o café entre 16:15 e 16:30 só como referência. Conferido no container: o mesmo dia dá 7h45
batendo ou não o café, e o painel conta o tempo de café em andamento. Não mexer.

## Pendências conhecidas

- **Controle de acesso:** `excluir_ponto` filtra pela equipe visível desde 23/11. Em 25/11,
  `aprovar_solicitacao` e `rejeitar_solicitacao` passaram a aceitar só pedido **pendente**, com
  bloqueio da linha (`select_for_update`); pedido já analisado volta para a lista com
  "Esta solicitação já foi analisada." Três testes novos. **Decisão do usuário (25/11):** por
  enquanto o gestor pode agir sobre qualquer equipe nas solicitações; não adicionar filtro de
  equipe nelas nem mudar `funcionarios_visiveis` sem novo pedido.
- **Testes locais:** o usuário do PostgreSQL local não tem permissão para criar o banco de
  teste. Em 25/11 a suíte rodou num container temporário com o código montado
  (`docker compose run --rm --no-deps -v "${PWD}:/app" -v /app/staticfiles --entrypoint python
  web manage.py test ponto`): 135 de 136, só a falha conhecida da foto de perfil.
- **Lint:** em 25/11 os imports e as linhas longas foram corrigidos, sem mudança de
  comportamento. Restam três avisos em `ponto/models.py`, deixados de propósito porque mudam
  o sistema: DJ008 (sem `__str__` em `HistoricoAlteracaoPonto` e `SolicitacaoAjustePonto`,
  muda o texto no admin) e DJ001 (`null=True` no `tipo` da solicitação, exige migração).
- **Próximos, combinados com o usuário em 25/11 para depois do próximo ajuste:** testes
  próprios do cálculo de horas e das permissões ([próximas coberturas](TESTES.md#próximas-coberturas))
  e a permissão para o usuário do PostgreSQL local criar o banco de teste.

## Ambiente local

- `.env` de desenvolvimento aponta para `postgres:postgres@localhost:5432/registro_ponto`.
- Banco `registro_ponto` (desenvolvimento do usuário): `admin`, e os colaboradores de teste
  `marina` e `rafael` (senha `teste-ponto-123`), com batidas de 26/10 a 18/11/2026.
- Conta `tech_leader` criada a pedido do usuário em 19/11: nome e função **Tech Leader**,
  papel **Gestor**, com **Rafael Lima** como subordinado. Senha inicial entregue na conversa;
  não registrada no repositório. Sem e-mail informado e sem acesso administrativo.
- Banco `registro_ponto_design`: dados fictícios usados para capturar as telas (`ana` gestora;
  `bruno`, `carla`, `diego`, `elisa` colaboradores; senha `senha-forte-123`). Para usar:
  `DB_NAME=registro_ponto_design python manage.py runserver 127.0.0.1:8766`. Pode ser apagado.
- O usuário roda o servidor pelo PyCharm na porta 8000; use outra porta para testes.
- Docker Desktop local configurado em 25/11 (depois de ativar a Plataforma de Máquina Virtual):
  `compose.yaml` publica a mesma porta 8000, por escolha do usuário, então PyCharm e Docker
  não rodam juntos. O banco do Docker é separado e começa vazio. Guia de comandos entregue em
  PDF na área de trabalho do usuário.
- Em 25/11 o `venv` do PyCharm recebeu as dependências de `requirements/development.txt`
  (faltava o `openpyxl` da importação de planilha). Reinstale ao puxar mudanças em `requirements/`.
- `.idea/` não é versionada; a configuração recomendada está em [Desenvolvimento](DESENVOLVIMENTO.md#pycharm).

## Design no Figcraft

`design/registro-ponto-telas.figcraft` é a fonte do desenho: página **Atual** (diagnóstico)
e **Proposta** (telas aprovadas, abas, PDF no iframe e direção visual). Para editar com o
usuário acompanhando:

```bash
figcraft --control 7710 design/registro-ponto-telas.figcraft   # abre a janela do app
figcraft-cli mcp --attach 7710                                  # servidor MCP ligado ao app aberto
```

Os scripts que montaram as pranchas eram temporários e não estão no repositório; edite o
arquivo pelo MCP (`create_node`, `set_properties`, `batch`, `screenshot`, `save_file`).
Se o usuário fechar o app, não reabra sem pedir. Exporte as prévias para `design/previas/`.

## Regras de trabalho combinadas

- Mudança visual nas telas passa primeiro pelo Figcraft. A revisão do cabeçalho foi autorizada
  pelo usuário para acomodar submenus e a largura de 1333 px. Login, cadastro público e
  redefinição de senha continuam preservados ([decisões](DECISOES.md)).
- CSS em `ponto/static/ponto/interno.css`: conteúdo sob `.principal-interno`, cabeçalho sob `.topo-aplicacao`.
- Formulários em `ponto/forms.py`, views em `ponto/views.py` e exceções em `ponto/exceptions.py`.
- Serviços em `ponto/services.py`, e-mail em `ponto/email.py` e testes somente em `ponto/tests.py`.
- Constantes em `ponto/constants.py`; lógica de apresentação em `ponto/services.py`.
- Ruff com 120 colunas; arquivos Python novos sem avisos.
- Commits em [Conventional Commits](PADROES_DE_DOCUMENTACAO.md#commits) em português, sem a
  linha `Co-Authored-By`, divididos por assunto. Desde 25/11 o próprio usuário faz commit e
  push: ao fim de cada mudança, entregue os comandos `git add` e as mensagens prontas, sem
  rodar `git commit` nem `git push`.
- Testes com Docker sobem em projeto e porta próprios e são removidos ao final (containers,
  volume, rede e imagens baixadas só para o teste).
- O xhtml2pdf ignora `vertical-align` e `valign` em células; para centralizar texto na grade
  do PDF, use `line-height: 1` e 2 px a mais de padding em cima ([comentário no template](../ponto/templates/ponto/relatorio_pdf.html)).

## Verificações antes de entregar

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test ponto
ruff check <arquivos alterados>
```

Para mudanças de tela, renderize a página com dados (banco de design) e compare com a prancha;
para o PDF, gere o arquivo e converta com `pdftoppm` para conferir.

## Revisão de 19/11 — jornadas e feriados

Administração ganhou **Jornadas** e **Feriados**. Migrações `0011` e `0012` aplicadas
no banco local; oito modelos semanais pré-carregados, sem atribuição automática.
Cadastro/edição de usuário permite vincular por vigência, com snapshots e histórico.
Sequência de batidas, painel e relatório usam a jornada individual. Jornadas dentro do
mesmo dia; 12×36 e noturnas ainda fora do suporte. Regras anteriores permanecem para
quem não foi vinculado, incluindo a divergência de carga já registrada nas pendências.
Feriados civis nacionais de 2026 carregados (nove datas); setup Docker sincroniza o ano
corrente localmente e a tela permite outros anos. Não existe sincronização com serviço
externo. [Uso, fontes e limites](USO.md#jornadas-e-feriados).
Validação: 43 testes distintos afetados aprovados, sem repetir a suíte completa;
cinco telas em três resoluções no Chrome e checks de Django/migrações aprovados.
Ajuste posterior na tela de Feriados: o rótulo Ano fica em linha própria e o input,
Consultar e Sincronizar nacionais compartilham a mesma linha, com topo, base e altura
iguais (48 px), usando classes existentes. Prancha **Feriados · Alinhamento dos controles**
no Figcraft e prévia em `design/previas/feriados-alinhamento/`.

## Revisão de 19/11 — folgas e banco de horas

Gestão ganhou **Folgas** (lista, lançamento e cancelamento; `gestor_required` em `views.py`).
Modelo `Folga` com migração `0013` aplicada nos bancos `registro_ponto` e
`registro_ponto_design`. Regras em `services.py`: `configuracao_jornada` considera a folga
(e aceita dados pré-carregados), `saldo_banco_horas` calcula o banco desde a primeira batida,
`aviso_do_dia` alimenta o aviso do painel e `efeito_da_folga` o quadro lateral do lançamento.
`formatar_timedelta` passou para `utils.py`. Fim de semana na regra anterior agora tem carga
zero. Prancha **Feriados e folgas** no Figcraft. [Uso e regras](USO.md#folgas-e-banco-de-horas).
Validação: 111 testes aprovados, checks de Django e migrações, telas renderizadas com dados.

## Revisão de 19/11 — instalação no servidor

Script e guia no commit `9aacf61`; esta página no commit seguinte. Ambos locais, sem push.

Cenário definido pelo usuário: Ubuntu Server 24.04, usuário padrão `prime` com acesso SSH por
senha (sem chave), IP interno, domínio apontado pela Cloudflare para o IP interno. Clone por
HTTPS com `usuário:token@github.com` (o GitHub não aceita senha; token fine-grained só leitura).
HTTPS pelo Let's Encrypt com validação DNS-01 da Cloudflare (token **Edit zone DNS**), porque a
internet não alcança o servidor; registro DNS precisa ficar em **DNS only**.

O script é interativo e idempotente: instala Docker, clona em `/opt/registro-ponto`, gera `.env`,
restringe a porta 8000 a `127.0.0.1` via `compose.override.yaml`, sobe os containers, cria o
administrador, configura Nginx com HTTPS, backup diário (`/var/backups/registro-ponto`, `700`,
`umask 077`) e sincronização anual de feriados. Rodar de novo atualiza sem trocar senhas.

Validação posterior: instalação e reexecução no Ubuntu 24.04 em Docker com systemd e daemon
próprio, backup restaurado, login e HTTPS com certificado local aprovados. Correção local:
`systemctl enable --now nginx`, porque recarregar o serviço parado interrompia o script.
Checks Django aprovados; 110 de 111 testes passaram na imagem. O teste de foto de perfil
recebe `application/octet-stream` em vez de `image/webp`, inclusive isoladamente.
ShellCheck executado, com três observações. [Procedimento e limites](TESTES.md#instalação-em-ubuntu-2404-no-docker--19112026).
Ainda falta VM completa e emissão/renovação real pela Cloudflare. Sem push.

## Implantação de 22/11 — HTTPS e renovação automática

Usuário conectado como `prime` em `srv-ponto`, Ubuntu 24.04.5 LTS, com sudo; domínio
`ponto.primecartorios.com.br`, IP interno `10.0.10.209`. Confirmou a criação do registro
DNS na Cloudflare e enviou o resumo de instalação concluída em `/opt/registro-ponto`,
inicialmente somente HTTP, sem token da Cloudflare.

**Decisão do usuário:** seguir com certificado Let's Encrypt por DNS manual e depois
automatizar a renovação com token da conta da empresa. O usuário edita DNS, mas não pode
criar Account API tokens; posteriormente recebeu o token da infraestrutura.
Certbot instalado; TXT publicado e conferido no DNS público do Google. Usuário enviou a
confirmação de certificado emitido, válido até **20/02/2027**, em
`/etc/letsencrypt/live/ponto.primecartorios.com.br/`. Reexecutou o instalador sem erros e
confirmou acesso HTTPS sem aviso e login com administrador. Pacote Nginx
`1.24.0-2ubuntu7.21`, configuração válida, serviço reiniciado e ativo. Câmera testada e
funcionando em produção, confirmado pelo usuário em 25/11.

**Renovação automática configurada:** plugin `python3-certbot-dns-cloudflare` instalado,
credencial em `/etc/letsencrypt/cloudflare.ini` com permissão 600. `certbot reconfigure`
migrou o certificado existente para `dns-cloudflare`, com propagação de 60 segundos e
deploy hook `nginx -t && systemctl reload nginx`. Usuário enviou simulação aprovada com
execução dos hooks e `Successfully updated configuration`. `certbot.timer` ativado e
agendamento confirmado para **23/11/2026 às 02h41min10s (-03)**. A primeira execução
agendada e uma renovação real ainda não foram observadas.
[Estado e procedimento](INSTALACAO.md#https-manual-e-automação-posterior--22112026).

Continuar orientando o usuário uma etapa por vez, aguardando a saída de cada etapa.

## Revisão de 23 a 25/11 — planilha, banco de horas e ajustes

Publicada em `origin/main` pelos PRs #2 a #4 e pelos commits de 25/11. Migração `0014`
(funções iniciais) entra em todo banco novo.

- **Importação de planilha retroativa** (`b5f89ee`, `8aaff08`): Meu ponto › Importar planilha
  de ponto recebe o `.xlsx` de banco de horas. O administrador encontra o colaborador pelo CPF
  da aba Resumo; o gestor escolhe o colaborador. Cada aba de mês vira batidas, inclusive o café.
  Dia com horários em 00:00 vira folga de compensação e dia com "S", folga negociada, salvo
  feriado. Nos dias importados a planilha prevalece: batidas existentes ficam inativas no
  histórico e folgas são canceladas. Datas futuras e horários fora de ordem viram avisos.
- **Saldo no cartão ponto** (`94638f8`): quadro Banco de horas abaixo dos totais do PDF, com
  extras, faltas, compensações, saldo do período e saldo acumulado.
- **Adicional de domingo** (`2a4a668`): domingo sem expediente previsto vale +100%; +40% se a
  semana seguinte tiver folga, feriado ou dia sem expediente não trabalhado. Entra no banco e
  nas EXTRAS do cartão, com a observação Dom. +100% ou Dom. +40%.
- **Banco de horas por mês de origem** (`9cde5c3`): Meu ponto › Banco de horas. Cada dia
  positivo forma um lote; compensações, faltas e dias abaixo da jornada consomem os lotes do
  mais antigo para o mais novo. Base para a validade das horas, ainda sem regra.
- **Exclusão pelo lançamento manual** (`1e0f856`) e **exclusão restrita à equipe visível**
  (`47690e4`).
- **Funções iniciais em todo banco novo** (`039f965`).
- **25/11:** decisão do café (conta como hora trabalhada; ver decisões pendentes), aprovação e
  rejeição só de pedidos pendentes (`8a7ad8e`), `venv` atualizado, Docker local e limpeza do
  Ruff sem mudança de comportamento.
