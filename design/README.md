# Proposta visual do conteúdo interno

Abra `registro-ponto-telas.figcraft` no Figcraft. A página **Atual** mostra as 12 telas
internas de hoje com o diagnóstico de cada uma; a página **Proposta** traz as mesmas telas
redesenhadas e a prancha **Direção visual**. As imagens em `previas/` permitem consultar
sem abrir o aplicativo. Nomes, horários e motivos são fictícios.

**Estado: Implementado em 18/11/2026.** As 12 telas estão nos templates, com o CSS em
`ponto/static/ponto/interno.css`. O header e as telas de login, cadastro e redefinição de
senha ficam como estão; as pranchas usam o recorte do header real.

## Telas

| Prancha | Principal mudança |
| --- | --- |
| Painel · colaborador | Linha do dia com as 6 batidas; o botão diz qual batida grava (“Registrar saída para o café”) |
| Painel · gestor | Aviso das solicitações pendentes e abas **Hoje**, **Ontem** e **Sua equipe** |
| Painel · abas Ontem e Sua equipe | Pranchas das outras abas da página inicial |
| Equipe | Tabela comparável: situação, as 6 batidas em células e horas trabalhadas |
| Lançar ponto manual | Formulário em duas colunas e as batidas que a pessoa já tem no dia |
| Excluir batida | Tela de confirmação no layout, com resumo da batida e motivo obrigatório |
| Solicitar ajuste | “Esqueci uma batida” e “Bati um ponto errado” lado a lado, agrupados por dia |
| Pedir exclusão | Confirmação no layout, com aviso de que a batida vale até a aprovação |
| Solicitações pendentes | Uma linha por pedido, com tipo, batida, motivo e **Rejeitar**/**Aprovar** alinhados |
| Solicitações pendentes · vazio | Estado vazio que explica quando os pedidos aparecem |
| Rejeitar solicitação | Confirmação no layout, com exemplo de erro de validação |
| Histórico de alterações | Coluna da batida alterada e filtros por colaborador, ação e período |
| Relatório de ponto | Filtro horizontal, nome completo no select, totais em destaque e situação por cor e texto |
| Relatório de ponto · PDF no iframe | **Gerar relatório** mostra o cartão ponto em PDF na própria página |

Três telas atuais (`excluir_ponto.html`, `solicitar_exclusao.html` e `rejeitar_solicitacao.html`)
não herdam o layout e abrem sem header nem CSS; a proposta as traz para dentro dele.

## Direção visual

- Figtree, como no Prime Central, com números tabulares nos horários.
- Fundo `#F2F5F9`, superfícies brancas, texto `#18324B` e apoio `#52677C`.
- Ação `#0A6EA3`: o azul da marca escurecido. O azul atual dos botões, `#03A9F5`, tem
  contraste de 2,63:1 com texto branco e reprova no
  [WCAG AA](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html);
  o novo tem 5,57:1.
- Verde `#17623F`, âmbar `#805100` e vermelho `#A62C35`, sempre acompanhados de texto,
  com fundos claros próprios. Todos os pares de texto e fundo passam de 4,5:1.
- Vermelho só para ações destrutivas e saldo devedor; hora extra deixa de aparecer em vermelho.
- Campos de 48 px, botões de 44 px, títulos à esquerda, conteúdo na largura de 1068 px do header.

A skill `frontend-design`, em `.ai/skills/`, orientou a proposta.

## Diferenças entre as pranchas e a implementação

| Item | Na aplicação |
| --- | --- |
| Batidas já registradas ao lançar ponto manual | Atualizam ao trocar a pessoa ou a data (`interno.js`) |
| “Mostrar mais 5 dias” em Solicitar ajuste | Vira **Mostrar os últimos 14 dias** e depois 30 |
| Header no celular | O header atual, sem adaptação: fica fora deste redesenho |

Toda nova mudança visual passa primeiro pelo Figcraft.

## Reconhecimento facial

A página **Câmera** contém as pranchas **Registrar por reconhecimento facial**,
**Ponto em computador compartilhado** e **Cadastrar rosto**. Foram desenhadas no Figcraft
antes da implementação, mantendo Figtree, cores, duas colunas e o header existente.
As prévias estão em `previas/camera/`. Na aplicação, o cadastro inclui seleção de pessoa,
remoção e explicação sobre o armazenamento; controles da câmera variam com seu estado.
As pranchas refletem a abertura e o registro automáticos, sem botões para identificar ou
gravar ponto. **Pausar câmera** e **Retomar câmera** permitem interromper e reabrir a captura;
o cadastro inicial do rosto continua confirmado pelo gestor.

## Administração e navegação

A página **Administração e navegação** reúne **Usuários**, **Cadastrar usuário** e
**Envio de e-mails**, desenhados em 1333 px antes da implementação. O usuário autorizou
revisar o cabeçalho: **Meu ponto**, **Gestão** e **Administração** abrem subitens por clique.
Cabeçalho e conteúdo deixam o limite de 1100 px e usam a largura disponível, com margens
laterais pequenas. O nome e a ação de sair têm espaço próprio. Prévias em
`previas/administracao/`. Essa revisão substitui a restrição anterior do header;
login, cadastro público e redefinição de senha permanecem como estavam.

## Colaborador e altura dos controles

Os textos das pranchas passaram a usar **Colaborador**. A prancha **Envio de e-mails**
foi ajustada antes do CSS para alinhar **Enviar teste** ao campo de destinatário: ambos
com 48 px de altura. As prévias de Administração e Câmera foram exportadas novamente.
As capturas históricas da página Atual representam o estado antigo da aplicação.
