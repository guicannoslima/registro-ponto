# Capacidade

Para 20 colaboradores simultâneos, o sistema roda com folga em **2 vCPU e 2 GB de RAM**; o
mínimo testado é **1 vCPU e 1 GB**, com respostas de 1 a 2 s quando PDFs e logins coincidem.

## Teste de carga — 18/11/2026

**Revisão:** `e90fa50`. **Ambiente:** stack Docker igual ao de produção (Gunicorn com 3
workers, PostgreSQL 17, `DEBUG=False`, WhiteNoise), numa máquina de 16 núcleos com 31 GB,
gerador de carga na mesma máquina. **Dados:** 20 colaboradores e uma gestora, com um mês de
batidas cada (2.640 batidas).

**Procedimento:** [Locust](https://docs.locust.io/) com 20 usuários simultâneos, cada um
logado como um colaborador diferente. Peso das ações: painel 6, aba Ontem 2, ajustes 2,
bater ponto 1, gerar relatório com o PDF no iframe 1 e baixar PDF 1 (os dois PDFs de 31
dias). CPU e memória dos containers amostradas a cada segundo com `docker stats`; a CPU está
em núcleos (1,0 = um núcleo inteiro).

| | Uso realista (2–5 s entre ações, 3 min) | Pico (sem pausa, 2 min) |
| --- | --- | --- |
| Requisições | 1.122 (6,2/s), 0 falhas | 4.026 (33,6/s), 0 falhas |
| Telas (mediana / p95) | 30–40 ms / 60–100 ms | 480–520 ms / ~1,2 s |
| PDF de 31 dias | ~500 ms | ~970 ms |
| Login | ~700 ms | ~1,5 s |
| CPU da aplicação | média 0,5; p95 1,2; máx 1,6 | 2,6–2,9 (3 workers no limite) |
| CPU do banco | média 0,1; máx 0,26 | média 0,4; máx 0,9 |
| Memória da aplicação | ~300 MiB (~100 MiB por worker) | ~305 MiB |
| Memória do banco | ~36 MiB | ~39 MiB |

## Leitura

- As telas comuns custam dezenas de milissegundos. O que pesa é o PDF (~0,5 s de CPU) e o
  login (~0,7 s), porque o hash de senha do Django é lento de propósito.
- A memória é fixa por worker e não cresce com a carga.
- Com 3 workers a aplicação não passa de ~3 núcleos; mais CPU só ajuda com mais workers.
  O banco nunca foi o gargalo.
- O pico é um extremo sintético (20 pessoas clicando sem parar); mesmo assim, sem erros.

## Limitações

Não verificado em vCPU de nuvem, que costuma ser mais lenta: os tempos podem subir 30–50%.
Sem latência de rede, e com só um mês de dados no banco. Para repetir, suba um stack isolado
(outra porta e outro nome de projeto no Compose), crie os usuários e rode o Locust com 20
usuários; remova o stack ao terminar.
