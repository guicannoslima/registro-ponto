# Padrões de documentação e escrita

Escreva para ajudar a pessoa a concluir uma tarefa ou entender uma decisão.
Comece pela resposta e confirme no código e na aplicação o comportamento descrito.
Vale para documentação, textos da interface, mensagens de commit e contribuições.

## Organização

Cada guia responde a uma pergunta. Nas duas primeiras linhas, apresente a resposta
ou a ação principal. Use um título de nível 1 por arquivo e seções de nível 2.
Use listas numeradas para passos em sequência e tabelas para comparar parâmetros.

| Assunto | Documento responsável |
| --- | --- |
| Visão geral e primeira execução | [README](../README.md) |
| Funcionalidades, papéis e rotas | [Uso](USO.md) |
| Módulos, modelos, permissões e regras de cálculo | [Arquitetura](ARQUITETURA.md) |
| Ambiente local, PyCharm, dependências e lint | [Desenvolvimento](DESENVOLVIMENTO.md) |
| Docker, variáveis de ambiente e dados | [Implantação](IMPLANTACAO.md) |
| Como reproduzir as verificações | [Testes](TESTES.md) |
| Por que cada caminho foi escolhido | [Decisões](DECISOES.md) |
| Estado e próximos passos | [Roadmap](ROADMAP.md) |

Atualize o documento responsável e aponte para ele a partir dos demais. Use links
relativos e, ao renomear uma página, atualize quem aponta para ela.

## Linguagem e nomenclatura

Use português direto, voz ativa e verbos concretos. Evite adjetivos promocionais,
"basta", "simplesmente" e promessas sem verificação. O produto é **Registro de Ponto**;
o projeto Django é `registro_ponto` e o app principal é `ponto`.
Identificadores técnicos mantêm a grafia do código.
Reproduza rótulos da interface em **negrito**, e use crases para comandos,
caminhos, parâmetros e valores.

Escreva durações no formato da aplicação (`7h45min`) e datas como `18/11/2026`.
Os papéis são **Funcionário**, **Gestor** e **Administrador**, como na interface.

## Afirmações e evidências

Descreva recursos com seu estado explícito: Implementado, Limitação conhecida,
Proposto ou Fora do escopo atual, conforme o [manual](README.md). Uma tela visível
ou um build concluído não comprovam o funcionamento de uma regra; confira no código
e, quando houver, no teste correspondente.

Em relatórios, registre data, versão ou revisão, ambiente, procedimento e resultado.
Marque como não verificado o que não foi exercitado. Ao citar uma biblioteca ou
ferramenta externa, mantenha o link para a documentação oficial junto da afirmação.

## Mensagens

Uma mensagem de erro identifica a operação que falhou e uma ação possível, como
"Você só pode bater ponto a cada 10 minutos.". Não declare sucesso após uma falha.
Estados vazios explicam o próximo passo, como registrar a primeira batida do dia.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/) em
português, com o verbo no presente e o assunto em minúsculas:
`feat: adiciona exportação do relatório em PDF`. Tipos usados: `feat`, `fix`,
`chore`, `docs`, `refactor` e `test`. O corpo, quando houver, explica o porquê.
