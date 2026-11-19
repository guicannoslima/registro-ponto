# Ponto de retomada

Estado em 18/11/2026, revisão `e90fa50` publicada em `origin/main`. Esta página diz o que já
foi feito, o que está pendente e como continuar o trabalho sem repetir o que já se decidiu.

## Onde o projeto está

| Área | Estado |
| --- | --- |
| Ambiente | Python 3.12 em `.venv`, Django 5.2 LTS, PostgreSQL local; Docker validado ([Implantação](IMPLANTACAO.md)) |
| Telas internas | Redesenhadas a partir da proposta aprovada no Figcraft ([design](../design/README.md)) |
| Página inicial | Abas **Hoje**, **Ontem** e **Sua equipe** (gestor), anel da jornada e linha do dia |
| Relatório | **Gerar relatório** mostra o cartão ponto em PDF num iframe; **Baixar PDF** baixa o arquivo |
| PDF | Cartão ponto no modelo de mercado, uma página por pessoa ([Uso](USO.md#relatório-de-banco-de-horas)) |
| Perfil | Todo usuário ganha perfil por signal ([decisão](DECISOES.md#perfil-criado-por-signal--18112026)) |
| Testes | 28 testes em `ponto/tests.py`, todos passando ([Testes](TESTES.md)) |
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
4. **Saudação do header:** usuários sem primeiro nome aparecem como "Bem-vindo, !". O header
   está congelado; só mudar se o usuário pedir.

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
- Banco `registro_ponto_design`: dados fictícios usados para capturar as telas (`ana` gestora;
  `bruno`, `carla`, `diego`, `elisa` funcionários; senha `senha-forte-123`). Para usar:
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

- Mudança visual nas telas passa primeiro pelo Figcraft; o header e as telas de login,
  cadastro e redefinição de senha não mudam ([decisão](DECISOES.md#conteúdo-interno-com-css-próprio--18112026)).
- CSS das telas internas em `ponto/static/ponto/interno.css`, sob `.principal-interno`.
- Constantes em `ponto/constants.py`; lógica de apresentação em `ponto/apresentacao.py`.
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
