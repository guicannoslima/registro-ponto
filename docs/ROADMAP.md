# Roadmap e pendências

As funcionalidades principais de ponto, ajustes e relatórios estão implementadas.
Esta página registra o estado de cada área e o que falta, na ordem de trabalho.

## Matriz atual — 18/11/2026

| Área | Estado | Próximo passo |
| --- | --- | --- |
| Batida automática e intervalo mínimo | Implementado, sem teste automático | Testes de `bater_ponto` |
| Painel com relógio de jornada | Implementado | — |
| Solicitações de inclusão e exclusão | Implementado, sem teste automático | Testes de aprovação e rejeição |
| Histórico de alterações e soft delete | Implementado | — |
| Relatório de banco de horas e PDF | Implementado, sem teste automático | Testes de `calcular_horas_dia` e do resumo |
| Cadastro, perfis e redefinição de senha | Implementado; perfil automático com testes | — |
| Docker (aplicação e PostgreSQL) | Implementado e verificado em 18/11/2026 | — |
| Lint com Ruff | Limitação conhecida: 31 avisos no código anterior | Rodar `ruff check --fix` e corrigir as linhas longas |
| Botão de exclusão na tela de ajuste de ponto | Proposto | Ajustar o botão |
| Redesenho do conteúdo interno | Implementado em 18/11/2026 ([design](../design/README.md)) | — |

## Ordem de trabalho

1. Ajustar o botão de exclusão na tela de ajuste de ponto.
2. Adequar o código ao Ruff: imports, linhas acima de 120 colunas e avisos de Django
   nos models.
3. Cobrir com testes as regras de horas, permissões e solicitações ([Testes](TESTES.md#próximas-coberturas)).

## Entregue

- Solicitação de inclusão e de exclusão de batida pelo colaborador.
- Aprovação e rejeição das solicitações pelo gestor.
- Tela de histórico de alterações.
- Relatório de banco de horas e exportação em PDF.
- Cadastro de usuários e redefinição de senha por e-mail.
- Tolerância de 10 minutos e limite das horas normais à jornada.
- Novo visual: login, cadastro, painel com relógio de jornada e menu por papel.
- Intervalo mínimo de 10 minutos entre batidas.
- Ambiente com Docker (aplicação e PostgreSQL).
- Perfil automático para todo usuário e Django 5.2 LTS.
- Redesenho das telas internas, com linha do dia, tabela da equipe e telas de confirmação.
