# Ponto de retomada

Estado em 18/11/2026, revisão `e90fa50` publicada em `origin/main`. Esta página diz o que já
foi feito, o que está pendente e como continuar o trabalho sem repetir o que já se decidiu.

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
O gestor precisa cadastrar os rostos reais antes do uso. Não há prova de vida
([uso e limitações](USO.md#registro-por-reconhecimento-facial)).

## Onde o projeto está

| Área | Estado |
| --- | --- |
| Ambiente | Python 3.12 em `.venv`, Django 5.2 LTS, PostgreSQL local; Docker validado ([Implantação](IMPLANTACAO.md)) |
| Telas internas | Redesenhadas a partir da proposta aprovada no Figcraft ([design](../design/README.md)) |
| Página inicial | Abas **Hoje**, **Ontem** e **Sua equipe** (gestor), anel da jornada e linha do dia |
| Relatório | **Gerar relatório** mostra o cartão ponto em PDF num iframe; **Baixar PDF** baixa o arquivo |
| PDF | Cartão ponto no modelo de mercado, uma página por pessoa ([Uso](USO.md#relatório-de-banco-de-horas)) |
| Perfil | Todo usuário ganha perfil por signal ([decisão](DECISOES.md#perfil-criado-por-signal--18112026)) |
| Testes | 88 testes em `ponto/tests.py`; 13 focados passaram na revisão de 19/11, sem repetir a suíte completa ([Testes](TESTES.md)) |
| Administração | Menu com Usuários e Envio de e-mails; cadastro/edição de contas, vínculo de equipe e SMTP |
| Reconhecimento facial | Verificação da pessoa logada, cadastro supervisionado e terminal restrito à equipe; pranchas na página **Câmera** do Figcraft |
| Capacidade | 2 vCPU e 2 GB para 20 pessoas simultâneas ([Capacidade](CAPACIDADE.md)) |

## Decisões pendentes do usuário

1. **Horário impresso no cartão:** `HORARIO_DE_TRABALHO` em `ponto/constants.py`
   (09:00–12:45, 14:00–16:15, 16:30–18:00) soma **7h30**, mas `JORNADA_DIARIA` é **7h45**.
   Perguntar qual vale antes de mexer.
2. **Sábado e domingo com batidas:** a regra atual espera 7h45 em qualquer dia com batida,
   então meio período no sábado gera saldo negativo (ex.: −3h45). Perguntar se fim de semana
   deve contar só como hora extra; é mudança de regra em `relatorios.py`.
3. **Atalho para dias incompletos:** a tabela do relatório na tela, com **Pedir ajuste** e
   **Lançar ponto**, saiu quando o PDF passou a ser exibido no iframe. Oferecido trazer uma
   lista curta acima do iframe; sem resposta.

## Pendências conhecidas

- **Controle de acesso (alta prioridade):** `excluir_ponto`, `aprovar_solicitacao` e
  `rejeitar_solicitacao` buscam o registro só pelo id. Um gestor consegue agir sobre pessoas
  fora da equipe trocando o id na URL, e uma solicitação já aprovada pode ser aprovada de novo
  (duplica a batida). Correção: filtrar com `funcionario__in=funcionarios_visiveis(request.user)`
  e, nas solicitações, `status=PENDENTE`, respondendo 404; cobrir com testes. Já existia antes
  do redesenho; o usuário foi avisado e ainda não pediu a correção.
- **Lint:** `ruff check .` acusa 20 avisos, todos de código anterior ao Ruff (linhas longas em
  `views.py` e `urls.py`, imports fora de ordem, avisos de Django nos models).
- **Testes de regra:** cálculo de horas e permissões ainda sem testes próprios
  ([próximas coberturas](TESTES.md#próximas-coberturas)).

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
  linha `Co-Authored-By`, divididos por assunto, e só quando o usuário pedir. Push também só
  quando pedido.
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
