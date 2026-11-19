# Orientações do projeto

Sistema web de registro de ponto da Prime Tecnologia, em Django 5.2 LTS com PostgreSQL. O app
`ponto` concentra modelos, views e telas; `registro_ponto` é a configuração. Comece pelo
[ponto de retomada](docs/RETOMADA.md): ele traz o estado atual, as decisões pendentes do
usuário e as regras de trabalho combinadas.

O [manual](docs/README.md) organiza uso, arquitetura, desenvolvimento, implantação, testes,
capacidade e decisões. Para documentação, mensagens e rótulos, siga os
[padrões de documentação e escrita](docs/PADROES_DE_DOCUMENTACAO.md).

## Contratos de código

- Regras de jornada, limites das telas e textos fixos ficam em `ponto/constants.py`.
- Dados prontos para as telas e para o PDF ficam em `ponto/services.py`; as views só montam
  o contexto.
- Todo usuário tem `Perfil` (signal em `ponto/signals.py`); as views leem `request.user.perfil`.
- O que cada papel enxerga vem de `funcionarios_visiveis` em `ponto/permissoes.py`.
- O CSS das telas internas fica em `ponto/static/ponto/interno.css`, sob `.principal-interno`;
  o cabeçalho revisado a pedido do usuário usa `.topo-aplicacao` no mesmo arquivo.
  `estilo.css` e as telas públicas não mudam.
- Formulários em `ponto/forms.py`, views em `ponto/views.py` e exceções em `ponto/exceptions.py`.
- Serviços de apresentação, sequência e gravação em `ponto/services.py`; e-mail em `ponto/email.py`.
- Todos os testes ficam em `ponto/tests.py`. O papel mostrado na interface é **Colaborador**.
- Ruff com 120 colunas (`pyproject.toml`); dependências em `requirements/` por ambiente.

## Antes de entregar

`python manage.py check`, `python manage.py makemigrations --check --dry-run`,
`python manage.py test ponto` e `ruff check` nos arquivos alterados. Mudanças de tela são
conferidas renderizando a página com dados e comparando com a prancha do Figcraft.
