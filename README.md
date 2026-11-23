# Registro de Ponto

Sistema web de controle de jornada da Prime Tecnologia, em Django e PostgreSQL:
o colaborador registra as batidas do dia com um clique, e gestores acompanham a
equipe, revisam ajustes e geram relatórios de banco de horas em tela ou em PDF.

**Estado: em desenvolvimento.** As funcionalidades principais estão implementadas;
as pendências estão no [roadmap](docs/ROADMAP.md).

## Executar

Com Docker, a aplicação e o PostgreSQL sobem juntos:

```bash
git clone https://github.com/primecartorios/registro-ponto.git
cd registro-ponto
cp .env.example .env               # preencha SECRET_KEY, DB_PASSWORD e e-mail
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Acesse `http://localhost:8000/`. Para rodar sem Docker, com PostgreSQL local e
PyCharm, veja [Desenvolvimento](docs/DESENVOLVIMENTO.md).

## Escopo

| Área | Estado |
| --- | --- |
| Batida automática na ordem do dia, com intervalo mínimo de 10 minutos | Implementado |
| Painel com relógio de jornada e hora extra | Implementado |
| Papéis **Colaborador**, **Gestor** e **Administrador** | Implementado |
| Solicitações de inclusão e exclusão, com aprovação e histórico | Implementado |
| Relatório de banco de horas e folha de ponto em PDF | Implementado |
| Cadastro de usuários e redefinição de senha por e-mail | Implementado |

## Requisitos

Docker com Compose, ou Python 3.12+ e PostgreSQL. Django 5.2 LTS; as dependências
ficam em `requirements/`, separadas por ambiente.

## Documentação

- [Manual completo](docs/README.md)
- [Uso: funcionalidades, papéis e rotas](docs/USO.md)
- [Arquitetura e regras de cálculo](docs/ARQUITETURA.md)
- [Implantação com Docker](docs/IMPLANTACAO.md)
- [Decisões de implementação](docs/DECISOES.md)

Desenvolvido por [Guilherme Cannos](https://github.com/guicannoslima).
