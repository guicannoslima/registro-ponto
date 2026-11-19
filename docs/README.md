# Manual do Registro de Ponto

O Registro de Ponto é uma aplicação web Django para controle de jornada da Prime Tecnologia.
Comece pelo [uso](USO.md) para conhecer as telas e pelo [desenvolvimento](DESENVOLVIMENTO.md) para rodar o projeto.
Para continuar o trabalho de onde parou, leia o [ponto de retomada](RETOMADA.md).

## Estado das informações

**Implementado** significa comportamento presente no código e verificável pelos
checks indicados. **Limitação conhecida** descreve algo que o produto ainda não
resolve. **Proposto** identifica um desenho técnico sem implementação. **Fora do
escopo atual** mantém registrado um tema sem prometer sua entrega.

Em 18/11/2026 o projeto roda com Django 5.2 LTS e PostgreSQL, localmente e no Docker.
A cobertura de testes automáticos ainda é pequena: as regras de horas e de
permissões estão descritas a partir do código, não de testes ([Testes](TESTES.md)).

## Uso

- [Funcionalidades, papéis e rotas](USO.md)
- [Implantação com Docker, variáveis de ambiente e dados](IMPLANTACAO.md)

## Engenharia

- [Arquitetura, modelos, permissões e regras de cálculo](ARQUITETURA.md)
- [Desenvolvimento local, PyCharm, dependências e Ruff](DESENVOLVIMENTO.md)
- [Testes](TESTES.md)
- [Capacidade e teste de carga](CAPACIDADE.md)
- [Padrões de documentação e escrita](PADROES_DE_DOCUMENTACAO.md)

## Planejamento

- [Ponto de retomada, pendências e regras de trabalho](RETOMADA.md)
- [Roadmap e pendências](ROADMAP.md)
- [Proposta visual do conteúdo interno (Figcraft)](../design/README.md)
- [Decisões de implementação](DECISOES.md)
