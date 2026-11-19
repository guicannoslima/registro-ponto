# Testes

**Implementado:** 69 testes reunidos em `ponto/tests.py`: perfil
automático, apresentação, views e fluxos faciais. As regras de cálculo de horas ainda
não têm testes próprios; a cobertura de permissões inclui os novos fluxos faciais.

## Executar

```bash
python manage.py test ponto
```

O Django cria um banco temporário `test_registro_ponto` no PostgreSQL do `.env`;
o usuário do banco precisa da permissão `CREATEDB`.

O test runner força `DEBUG=False`, e o storage do WhiteNoise exigiria o
`collectstatic`. As classes de teste usam `override_settings` com o
`StaticFilesStorage` simples para renderizar as telas sem esse passo.

## Cobertura atual

| Teste | Verifica |
| --- | --- |
| `test_superusuario_recebe_perfil_de_administrador` | `createsuperuser` gera perfil **Administrador** |
| `test_usuario_comum_recebe_perfil_de_funcionario` | `create_user` gera perfil **Colaborador** |
| `test_superusuario_acessa_o_painel_sem_erro` | O painel abre para o superusuário (status 200) |
| `test_cadastro_pela_tela_preenche_o_perfil_criado_automaticamente` | O cadastro grava CPF e função num perfil único |
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
