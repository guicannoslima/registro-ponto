# Testes

**Implementado:** 89 testes reunidos em `ponto/tests.py`: perfil
automático, apresentação, views e fluxos faciais. As regras de cálculo de horas ainda
não têm testes próprios; a cobertura de permissões inclui os fluxos faciais e os relatórios.

## Executar

```bash
python manage.py test ponto
```

O Django cria um banco temporário `test_registro_ponto` no PostgreSQL do `.env`;
o usuário do banco precisa da permissão `CREATEDB`.

O test runner força `DEBUG=False`, e o storage do WhiteNoise exigiria o
`collectstatic`. As classes de teste usam `override_settings` com o
`StaticFilesStorage` simples para renderizar as telas sem esse passo.

## Instalação em Ubuntu 24.04 no Docker — 19/11/2026

**Verificado:** `scripts/instalar.sh` da revisão `52446f3`, com a correção local
`systemctl enable --now nginx`, concluiu a instalação e a reexecução num Ubuntu 24.04
descartável. O Nginx parado revelou que `enable` sozinho não inicia o serviço;
a correção inicia o Nginx antes de recarregá-lo.

O contêiner executou systemd e um daemon Docker próprio, sem montar o socket Docker
da máquina. A base recebeu `sudo`, cron e SSH para representar o servidor, com usuário
`prime` e sudo sem autenticação para automatizar o teste. Docker 29.10.0 e Compose 5.8.0
foram instalados pelo script. O armazenamento interno usou `vfs`, pois o armazenamento
padrão falhou ao extrair uma camada no Docker aninhado. O clone foi redirecionado por
`git insteadOf` para uma cópia local do repositório; todas as credenciais eram fictícias.
As portas externas ficaram restritas a `127.0.0.1:18080` e `127.0.0.1:18443`.
O contêiner, seus recursos internos e as imagens externas exclusivas do teste foram
removidos ao final; os contêineres preexistentes permaneceram em execução.

Procedimento: executar o instalador sem certificado; entrar pelo Nginx com o administrador;
gravar um arquivo de mídia; executar e restaurar o backup; provisionar certificado
autoassinado de teste; reexecutar o instalador; comparar configuração, senhas e agendamentos.

| Verificação | Resultado |
| --- | --- |
| Instalação desde banco vazio, com Nginx inicialmente parado | Saída 0; administrador criado; 31 migrações aplicadas |
| Serviços e firewall | Docker, containerd, Nginx e cron ativos; UFW ativo com SSH, HTTP e HTTPS |
| Acesso | Login com CSRF retorna 302; painel autenticado e login via proxy retornam 200 |
| Porta da aplicação | Somente `127.0.0.1:8000` dentro do servidor de teste |
| Permissões | `.env` e `.git/config`: 600; pasta de backups: 700; dump e arquivo de mídia: 600 |
| Backup | Dump restaurado num segundo banco; administrador recuperado; conteúdo do arquivo de mídia conferido |
| Reexecução | Saída 0; hashes do `.env` e das senhas preservados; mídia preservada; somente duas linhas no crontab |
| HTTPS com certificado local | Login retorna 200 validando o certificado de teste; HTTP retorna 301 para HTTPS |
| Django | `check` aprovado; `makemigrations --check --dry-run` sem alterações |
| Suíte na imagem instalada | 110 de 111 testes aprovados; falha de tipo de conteúdo descrita abaixo |
| Shell | `bash -n` aprovado; ShellCheck aponta SC2015 nas linhas 81/324 e SC2016 na linha 239 |

**Limitação conhecida:** `FotoPerfilTests.test_fotos_sao_privadas_e_limitadas_a_equipe`
recebe `application/octet-stream` em vez de `image/webp` na imagem de produção.
O teste também falhou isoladamente. A aplicação não foi alterada nesta validação do instalador.

**Não verificado:** autenticação real no GitHub, envio Gmail, emissão/renovação do Let's Encrypt
pela Cloudflare, execução dos agendamentos pelo relógio e reinicialização de uma VM completa.
O certificado autoassinado verifica a configuração HTTPS do Nginx, sem validar DNS-01.
Se a primeira execução parar depois de gerar `.env` e antes de criar o administrador,
a reexecução pula a criação da conta; nesse caso, use `docker compose exec web python manage.py createsuperuser`.

## Cobertura atual

| Teste | Verifica |
| --- | --- |
| `test_superusuario_recebe_perfil_de_administrador` | `createsuperuser` gera perfil **Administrador** |
| `test_usuario_comum_recebe_perfil_de_funcionario` | `create_user` gera perfil **Colaborador** |
| `test_superusuario_acessa_o_painel_sem_erro` | O painel abre para o superusuário (status 200) |
| `test_cadastro_pela_tela_preenche_o_perfil_criado_automaticamente` | O cadastro grava CPF e função num perfil único |
| `test_cadastro_lista_as_funcoes_iniciais` | O cadastro lista as quatro funções que a migração `0014` cria em todo banco novo |
| `ApresentacaoTests` (5) | Linha do dia, situação, saldo com sinal, junção de nomes e fim de semana fora do relatório |
| `TelasInternasTests` (8) | Botão com a próxima batida, aviso de pendências, equipe, batidas no lançamento manual, exclusão, rejeição sem motivo, filtro do histórico e nome completo no relatório |

## Verificações antes do commit

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test ponto
ruff check .
```

## Próximas coberturas

**Proposto**, na ordem de risco:

1. `calcular_horas_dia`: dia completo, sem almoço, dentro e fora da tolerância.
2. `funcionarios_visiveis`: alcance de cada papel.
3. `bater_ponto`: ordem das batidas, intervalo mínimo e dia completo.
4. Aprovação e rejeição de solicitações, com o registro no histórico.

## Reconhecimento facial — 18/11/2026

**Verificado:** Python 3.12, PostgreSQL local, OpenCV 4.13.0.92, YuNet e SFace com hashes
conferidos. `check`, `makemigrations --check --dry-run` e os 47 testes passaram. O Ruff
não aponta avisos novos nos arquivos alterados; permanecem 11 avisos anteriores nesses
arquivos. Não houve commit nem push.

Os 19 testes novos verificam: renderização, batida pessoal, rosto de outra pessoa, motor
indisponível, ausência de cadastro, autorização por papel/equipe, substituição e remoção,
rosto já associado a outra conta, sessão restrita do terminal, revogação ao desativar o
responsável, CSRF, imagens inválidas/grandes e identificação desconhecida ou ambígua.
Os testes de views substituem a extração do vetor; não medem a precisão do modelo.

Em exercício separado com o motor real e imagens públicas dos exemplos OpenCV (`lena.jpg`
e `messi5.jpg`), o vetor teve 128 posições e norma 1; a similaridade da mesma pessoa em
outro tamanho foi 0,9603 e entre pessoas diferentes foi 0,0873. Uma imagem sem rosto foi
rejeitada. Esses exemplos verificam a integração, sem representar uma avaliação de precisão.

No Chrome, com banco de design e câmera simulada pela imagem pública, foram exercitados:
falha sem câmera, cadastro, identificação e gravação de batida no terminal, bloqueio de
uma segunda batida pelo intervalo mínimo, acesso à gestão negado no terminal, encerramento
e remoção do cadastro de teste. Sem erros JavaScript. Telas capturadas em 1440 e 390 px
para comparação com o Figcraft; o header existente continua sem adaptação no celular.

**Não verificado:** webcam física, iluminação real, precisão para os colaboradores e carga
simultânea do reconhecimento. A estimativa de capacidade anterior não mede esse processamento.

### Registro e abertura automáticos — 18/11/2026

**Verificado:** 50 testes passaram, sem mudanças de migração; `check` e Ruff nos arquivos
Python desta continuação passaram. Três testes adicionais cobrem permanência da mesma
pessoa por mais de 10 minutos sem duplicar a batida, liberação após ausência de rosto e
identificação de pessoas diferentes em sequência.

No Chrome, com banco de design e câmera simulada, a tela abriu a câmera sem clique,
o terminal identificou e gravou o ponto automaticamente pelo motor real, conservou a
confirmação nas capturas seguintes e detectou a saída do enquadramento. A pausa interrompeu
as capturas seguintes. O modo pessoal recebeu o bloqueio real do intervalo de 10 minutos;
para conferir o encerramento após sucesso pessoal sem criar outra batida de teste,
apenas a resposta de gravação desse cenário foi simulada. A permissão negada foi tratada
com orientação e opção de retomar. Não houve erros JavaScript. Os cadastros e a batida
criados pelo exercício foram removidos do banco de design.

### Administração, menu e SMTP — 18/11/2026

**Verificado:** 69 testes passaram após reunir os formulários em `forms.py`, views em
`views.py` e exceções em `exceptions.py`. `check` e a conferência de migrações passaram.
Os 19 testes de administração cobrem cadastro e edição de usuário, e-mail, senha, CPF,
papel, gestor, desativação, proteção da própria conta, busca, CSRF, acesso aos menus,
SMTP cifrado, preservação/remoção de senha, dados inválidos, falha de envio, uso do ambiente
e aplicação da configuração SMTP e do remetente na recuperação de senha.

No Chrome, com dados fictícios no banco de design, foram conferidos: cadastro e edição,
salvamento SMTP com campo de senha vazio na resposta, submenus por clique, `Escape`, clique
fora e apenas um aberto, largura integral de 1333 px e ausência de rolagem horizontal
na página em 390, 768 e 1333 px. As tabelas mantêm rolagem própria quando necessário.
Capturas foram comparadas às pranchas do Figcraft. Nenhum e-mail real foi enviado; os
exercícios SMTP automáticos usam simulação. A entrega real depende do provedor e das
credenciais configuradas pelo administrador.

### Arquivos reunidos e controles alinhados — 18/11/2026

**Verificado:** os mesmos 69 testes passaram, agora todos em `ponto/tests.py`, após reunir
apresentação, sequência e gravação em `services.py` e renomear o módulo para `email.py`.
A cobertura do perfil também confere o rótulo **Colaborador**. O `check` e a conferência
de migrações passaram; a migração `0009` atualiza apenas rótulos dos modelos e formulários.

No Chrome, a tela de SMTP foi conferida em 1333, 2048 e 390 px. O campo de destinatário e
**Enviar teste** mediram 48 px cada; nos dois tamanhos de desktop, a diferença entre os
topos foi 0 px. No celular ficam empilhados com 16 px de intervalo. A busca de usuários
também manteve campo e botão com 48 px e topos alinhados. Conferidos os rótulos **Colaborador**
no cadastro de usuários, na lista de contas e no lançamento manual. Sem erros JavaScript
ou envio de e-mail; a conta fictícia foi removida ao final.

### Serviço de registro facial — 18/11/2026

**Verificado:** 71 testes passaram com `registrar_ponto_facial` em `services.py` e as
views pessoal e de terminal usando esse serviço. Dois testes adicionais exercitam o
registro diretamente, sem requisição HTTP, e a ausência de cadastro antes do processamento
da imagem. As regressões existentes conferem rostos desconhecidos, erro do motor, intervalo
mínimo, identificação restrita à equipe e presença contínua sem duplicar batidas.
O teste de ausência de cadastro também confere que a resposta manda interromper as tentativas.
`check`, conferência de migrações e Ruff nos serviços, utilitários, exceções e testes passaram.

### Estado do cadastro por colaborador — 18/11/2026

**Verificado:** 74 testes passaram. Três coberturas adicionais conferem consulta de
cadastrado/sem cadastro sem retornar vetores biométricos, acesso restrito por papel/equipe
e indicação de cadastro na lista. As respostas de salvar e remover também informam o
estado final, e uma nova consulta após a remoção confirma a ausência do cadastro.
`check`, conferência de migrações e Ruff nos serviços e testes passaram. Sem migração nova.

No Chrome, com câmera simulada e colaboradores fictícios do banco de design, foram
conferidos: estado inicial, troca entre pessoas cadastradas e sem cadastro, resposta
atrasada ignorada, ações bloqueadas enquanto se consulta, cadastro e substituição pelo
motor real, cancelamento da substituição, remoção sem câmera e atualização imediata dos
rótulos. A seleção ficou bloqueada durante o envio. Falha de consulta mostrou estado
indeterminado e manteve as ações bloqueadas. Conferidas telas em 1333 e 390 px sem
rolagem horizontal nem erros JavaScript. Os dados fictícios foram removidos ao final.

### Foto escolhida e confirmação por 3 segundos — 18/11/2026

**Verificado:** 82 testes passaram. Oito testes adicionais cobrem foto escolhida pelo
colaborador, normalização, rejeição de arquivo inválido, substituição/remoção dos arquivos,
acesso privado por pessoa/equipe, foto no terminal apenas após confirmação, uso do primeiro
nome, imagem genérica sem foto e atalhos de gestão fora da página inicial. `check` e a
conferência de migrações passaram; a migração `0010` foi aplicada no banco local.

No Chrome, com pessoas fictícias e câmera simulada por imagens públicas do OpenCV, foram
verificados upload e remoção pelo próprio perfil, reconhecimento real e exibição da foto
escolhida e da imagem genérica com o nome. Um observador das mudanças de visibilidade mediu
3000 ms em ambos os casos. **Retomar câmera** ficou bloqueado durante a confirmação; o
terminal não repetiu a imagem ao reconhecer a mesma pessoa. Conferidos primeiro nome em
caixa alta sem tipo/horário, ações de gestão somente no menu e tela em 390 px sem recorte ou
rolagem horizontal. Sem erros JavaScript; os dados fictícios foram removidos ao final.

### Diálogos, WebP, CPF e acesso aos relatórios — 18/11/2026

**Verificado:** executados somente os testes relacionados aos pedidos: `FotoPerfilTests`,
`RelatorioPermissoesTests`, cadastro administrativo com CPF e dois testes de geração do
cartão em PDF. **16 testes passaram** no PostgreSQL. A suíte agora tem 87 testes; os demais
não foram repetidos nesta revisão, conforme solicitado. A última execução completa
anterior foi a de 82 testes descrita acima.

Os novos casos conferem conversão de PNG e WebP para WebP de 512 × 512 sem metadados,
Content-Type da foto, seleção por papel/equipe, visualização e download do PDF,
tentativa de trocar o id e envio de `gerar_todos` sem autorização. Administrador vê todos,
gestor vê subordinados e colaborador vê somente a si.

No Chrome em 1333 e 390 px, com câmera simulada, banco SQLite e fotos isolados em `/tmp`,
foram conferidos: diálogo da aplicação sem `window.confirm`, substituição cancelada por
Escape, remoção cancelada e confirmada, foco inicial em Cancelar, alinhamento dos controles
de busca, CPF digitado/colado/editado, exclusão na largura do layout, faixa facial em toda
a linha, menus por papel e upload servido em WebP. Sem rolagem horizontal ou erros JS.
O registro 197 do banco do usuário não foi alterado. O servidor, o banco e as fotos
temporários foram removidos ao encerrar a validação.

`check`, `makemigrations --check --dry-run`, sintaxe JavaScript e `git diff --check`
passaram. Ruff passou em forms, services e testes; views conserva os dois avisos de linha
longa anteriores a esta revisão. A imagem Docker foi construída, e um contêiner descartável
sem rede confirmou SHA-256, carregamento dos dois modelos OpenCV e suporte WebP.

### Avisos da câmera e redução de fotos grandes — 19/11/2026

**Verificado:** 13 testes focados passaram: `FotoPerfilTests` e os três casos de telas,
ausência de cadastro e substituição/remoção em `FluxosFaciaisTests`. Fotos reais geradas
com 5000 × 4000 pixels, em JPEG, PNG e WebP, foram aceitas e reduzidas para WebP de
512 × 512. Mantidos os limites de arquivo e as proteções do decodificador. A suíte agora
contém 88 testes; os demais não foram repetidos.

No Chrome em 1333 e 390 px, com HTML renderizado pelo Django, câmera e respostas de API
simuladas, o aviso de cadastro ausente permaneceu visível mesmo sem câmera. A confirmação
verde do cadastro apareceu por 3001 ms; depois, seleção e retomada da câmera foram
liberadas. Conferidos ausência de recorte e de erros JavaScript. Não foram cadastrados
rostos reais nesse teste de interface.

No banco local, a conta solicitada `tech_leader` foi conferida com papel Gestor, função
Tech Leader e somente Rafael na equipe. Sem privilégios de administrador ou superusuário.

### Aviso de intervalo sobre a câmera — 19/11/2026

**Verificado:** no Chrome, com HTML do Django e resposta 409 simulada, o aviso de intervalo
ocupou a largura da prévia em sua parte inferior, com fundo de opacidade 88%, em 1333 e
390 px. A câmera permaneceu visível durante o aviso; não houve nova captura nesse período.
A camada desapareceu e limpou seu texto após 6001 ms; Retomar câmera iniciou uma nova
tentativa corretamente. Sem erros JavaScript ou rolagem horizontal. Nenhum ponto real
foi gravado ou removido. O teste focado `FluxosFaciaisTests.test_telas_renderizam` passou;
sintaxe JavaScript e `git diff --check` passaram. Ruff mantém apenas as duas linhas longas
preexistentes em views, sem novos avisos.

### Confirmação pessoal sem mensagem duplicada — 19/11/2026

**Verificado:** no Chrome, com resposta de sucesso simulada, a confirmação pessoal foi
exibida por aproximadamente 3 segundos. Após ocultar o cartão, o texto abaixo da prévia
ficou vazio e oculto, e Retomar câmera permaneceu disponível. Sem erros JavaScript;
nenhuma batida real foi registrada. Sintaxe JavaScript e `git diff --check` passaram.

### Demais mensagens no rodapé da câmera — 19/11/2026

**Verificado:** no Chrome em 1333 e 390 px, os avisos de abertura, câmera ausente e pausa
ficaram dentro da prévia, na mesma camada inferior transparente, sem parágrafo entre a
prévia e Retomar câmera. Conferidos alinhamento à borda inferior, largura da camada,
botão disponível após pausa e ausência de rolagem horizontal ou erros JavaScript.
Teste com câmera e respostas simuladas, sem alterar o banco.

### Retomar câmera por clique ou toque — 19/11/2026

**Verificado:** Chrome em contexto desktop de 1333 px e móvel de 390 px com toque. Após
falha inicial simulada, clicar ou tocar na prévia inteira retomou a câmera; o botão
Retomar câmera continuou funcionando. Enter na área focada também abriu a câmera.
Dois cliques rápidos dispararam apenas uma abertura; a área ficou desabilitada com a
câmera ativa. Sem erros JavaScript. Câmera e respostas simuladas, sem batidas reais.
Sintaxe JavaScript e `git diff --check` passaram.

### Terminal contínuo e repouso da câmera — 19/11/2026

**Verificado:** 23 testes de `FluxosFaciaisTests` passaram. Incluem a renovação após 13 horas
sem criar batidas, encerramento que invalida a manutenção, acesso revogado ao desativar
o gestor, botão único no cabeçalho, ausência do painel lateral e prevenção de duplicações.
A suíte contém 89 testes; os demais não foram repetidos nesta revisão.

No Chrome com HTML do Django, câmera e respostas simuladas, a webcam foi pausada após
30019 ms reais sem atividade: tracks encerradas, capturas interrompidas e terminal aberto.
Conferidos retomada por toque, uso de Retomar câmera, reconhecimento após a confirmação,
cabeçalho com encerramento e telas em 1333 e 390 px sem rolagem horizontal.
Com relógio simulado instalado antes da navegação, toque renovou os 30 segundos,
respostas sem rosto não renovaram, a manutenção respondeu após 5 minutos com webcam
pausada e o botão do cabeçalho encaminhou o encerramento. Sem erros JavaScript.
Nenhum rosto ou ponto real foi criado por essa validação de interface.

### Terminal sem título e sem rolagem — 19/11/2026

**Verificado:** no Chrome, com HTML do Django e câmera/API simuladas, o terminal coube em
12 viewports: 1333×768, 1920×1080, 1024×768, 768×1024, 820×1180, 1180×820, 390×844,
844×390, 360×640, 640×360, 320×568 e 568×320. Sem rolagem vertical ou horizontal e sem
ocultar controles fora da tela; altura calculada pelo layout, sem mascarar overflow da página.
Título e introdução ausentes. Conferidos também o cartão de confirmação e imagem genérica
em desktop, tablet, celular e celular horizontal, sem recorte. Sem erros JavaScript.
Nenhuma batida real foi registrada. `git diff --check` passou.

### Preenchimento da prévia em tablet e celular — 19/11/2026

**Verificado:** no Chrome, com vídeo simulado de 640×480, a prévia usou preenchimento
proporcional com recorte central em 390×844, 768×1024, 1366×1024 com toque e 844×390.
Elemento de vídeo ocupando integralmente o quadro, sem esticar ou alterar a captura de
origem. Em desktop de 1333×768 sem toque, mantida a exibição integral anterior. Sem
rolagem horizontal/vertical nem erros JavaScript. Conferida captura de tela em celular.
`git diff --check` passou. Alteração somente de apresentação; sem batidas reais.

### Guia minimalista de posicionamento do rosto — 19/11/2026

**Verificado:** no Chrome, nas prévias pessoal, de cadastro e de terminal, em 1333×768,
390×844 e 844×390. Guia de quatro cantos com enquadramento quadrado central, traço cinza
claro semitransparente e sem preenchimento. Os cantos permanecem dentro da prévia em
retrato e paisagem, não bloqueiam os eventos de ponteiro e desaparecem ao pausar a câmera.
Retomada por toque funcionando nos nove cenários; sem erros JavaScript. Câmera e API
simuladas, sem gravações reais. Conferida captura visual do terminal móvel.
`git diff --check` e sintaxe JavaScript passaram. A referência visual não foi incorporada
como imagem ao sistema; o guia é SVG da própria interface.

### Respostas repetidas não renovam a inatividade — 19/11/2026

**Verificado:** no Chrome com relógio e API simulados, respostas 200 com `repetido: true`
não reiniciaram os 30 segundos. Conferidos tanto presença já conhecida desde a primeira
resposta quanto uma batida nova seguida de respostas repetidas. A câmera foi pausada,
as tracks encerradas e não houve novas capturas após a pausa; o terminal permaneceu
aberto. Sem erros JavaScript. Nenhuma batida real criada; sintaxe JS e diff conferidos.

### Foto ampliada na confirmação — 19/11/2026

**Verificado:** no Chrome com foto e API simuladas, a imagem permaneceu quadrada, sem
recorte ou sobreposição do título: 382×382 no terminal 1333×768, 512×512 em 768×1024,
289×289 em 390×844, 177×177 em 844×390 e 107×107 em 568×320. No modo pessoal: 268×268
em 1333×768 e 109×109 em 390×844. Confirmados foto dentro da prévia, ausência de
rolagem no terminal e de erros JavaScript. Mantida a duração de 3 segundos; alteração
somente de CSS. Nenhuma nova batida real foi gravada pela verificação de interface.
`git diff --check` passou.

## Jornadas e feriados — 19/11/2026

Foram executados 40 testes afetados: `JornadasFeriadosTests`, `CartaoPontoTests` e
`AdministracaoTests`, todos aprovados. A expectativa antiga do menu foi atualizada:
o gestor tem Administração para abrir o terminal, mas não vê os novos cadastros.
A suíte completa não foi repetida. As coberturas novas verificam modelos iniciais,
validação de horários, vigência e snapshot, carga individual, sequência sem café,
feriado sem falta e com extras, progresso com carga zero, permissões e inativação.
Verificações adicionais cobrem sincronização pela tela, datas duplicadas e reaplicação.

As cinco telas foram renderizadas com leitura do banco local e conferidas no Chrome
headless a 1333, 768 e 390 px: sem transbordamento da página ou campos e sem erros JS.
As capturas temporárias ficaram em `/tmp/ponto-jornadas-browser/`; nenhuma batida ou
vínculo real foi criado nessa verificação. Pranchas em [design](../design/README.md#jornadas-e-feriados).

Resultado final: 43 testes distintos afetados aprovados — os 40 acima e os três casos
adicionais de sincronização/cadastro/reaplicação; a última execução isolada teve 15 testes
em `JornadasFeriadosTests`, todos aprovados. Django check e verificação de migrações
passaram. Ruff sem novos avisos; os avisos antigos de models, views e relatórios permanecem.
