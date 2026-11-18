# Testes

**Implementado:** 17 testes em `ponto/tests.py`: perfil automático, apresentação das
telas internas e comportamento das views. As regras de cálculo de horas e de permissões
ainda não têm testes próprios.

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
| `test_usuario_comum_recebe_perfil_de_funcionario` | `create_user` gera perfil **Funcionário** |
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
