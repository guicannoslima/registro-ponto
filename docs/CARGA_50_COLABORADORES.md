# Carga de 50 colaboradores simultâneos

**Recomendação para a VM: 4 vCPU e 4 GB de RAM, com aplicação e PostgreSQL na mesma máquina.**
O cenário menor, de 2 CPUs e orçamento de 2 GB, também concluiu todas as batidas; 4 vCPU
oferecem margem para o pico. Os 4 GB são margem operacional, não consumo medido obrigatório.

## Resultado — 19/11/2026

**Revisão:** `ecebb54`, sem alterações no código da aplicação para o teste.
**Estado:** executado em Docker, com reconhecimento facial real, sem mocks de IA.

Cada rajada teve 50 contas distintas, com POSTs liberados por uma barreira. O maior
intervalo observado entre o primeiro e o último disparo foi de 37,3 ms. Foram medidos
**1.200 POSTs: 150 logins e 1.050 registros de ponto**, todos bem-sucedidos. Depois de cada
rajada de ponto, o banco confirmou exatamente **50 batidas, 50 colaboradores e zero
duplicações**. Não houve timeout, encerramento por memória ou reinício de worker.

**p95** significa que 95% das respostas terminaram em até esse tempo. As colunas de ponto
usam pessoas já autenticadas; login é medido separadamente.

| CPUs / orçamento de RAM | Botão: p95 | Facial aquecido: p95 | Facial com motor frio: p95 | 50 logins: p95 |
| --- | ---: | ---: | ---: | ---: |
| 2 / 2 GB | 0,45 s | 1,47 s | 1,73 s | 9,24 s |
| 4 / 4 GB | 0,28 s | 0,90 s | 1,12 s | 6,18 s |
| 8 / 8 GB | 0,29 s | 0,73 s | 0,95 s | 6,36 s |

Botão e facial aquecido: p95 calculado sobre 150 respostas de três rajadas por
configuração. Motor frio: primeira rajada de 50 reconhecimentos após iniciar os workers;
o Django e os logins já estavam aquecidos. Login: uma rajada de 50 por configuração.

## CPU e memória

| Configuração | CPU média da aplicação no facial | CPU média do banco no facial | Pico de memória da aplicação | Pico de memória do banco |
| --- | ---: | ---: | ---: | ---: |
| 2 CPUs | 1,56 núcleo | 0,37 núcleo | 596 MiB | 34 MiB |
| 4 CPUs | 2,94 núcleos | 0,61 núcleo | 597 MiB | 38 MiB |
| 8 CPUs | 4,93 núcleos | 0,78 núcleo | 599 MiB | 39 MiB |

CPU: média das três rajadas faciais aquecidas, em núcleos ocupados. Memória: maior amostra
observada em todas as fases, descontando cache de arquivo inativo, como no Docker Stats.
A soma dos picos de aplicação e banco ficou abaixo de 640 MiB; sem descontar esse cache,
a soma ficou abaixo de **700 MiB**. Os picos de cada contêiner podem ocorrer em instantes
diferentes. Não estão incluídos o sistema operacional da futura VM nem o gerador de carga.

No cenário de 2 CPUs, o facial ocupou quase toda a CPU disponível durante a rajada. Com
4 CPUs, o p95 caiu de 1,47 para 0,90 s. Dobrar novamente para 8 CPUs reduziu para 0,73 s,
mas não melhorou botão ou login de maneira relevante com os mesmos três workers.
Não houve necessidade de 8 GB de memória para este teste.

## Configuração indicada

- **VM recomendada:** 4 vCPU e 4 GB de RAM, para aplicação, PostgreSQL e sistema operacional.
- **Menor cenário aprovado neste ensaio:** 2 CPUs / orçamento de 2 GB, adequado ao ponto
  já autenticado, com menos folga durante reconhecimento facial e login simultâneo.
- **Aplicação:** Gunicorn com os mesmos **3 workers síncronos** do Dockerfile, timeout
  padrão de 30 s. Não foi necessário modificar o código ou o limite entre batidas.
- **8 vCPU / 8 GB:** não se justifica apenas para o pico de 50 batidas medido aqui.

Se todos também precisarem entrar no sistema ao mesmo tempo, o login será a espera maior:
cerca de 6,2 s no p95 com 4 CPUs. Esses tempos não estão embutidos no p95 do ponto.
Alterar o número de workers pode mudar esse comportamento e precisa de novo ensaio;
este relatório não atribui os resultados a uma configuração que não foi testada.

## Como o ensaio foi feito

Host Intel Core i9-9900K de 3,60 GHz, 8 núcleos físicos / 16 CPUs lógicas e aproximadamente
32 GB de RAM. Outros serviços existentes no host permaneceram em execução. O gerador
ficou no mesmo host, com afinidade nas CPUs 6, 7, 14 e 15; no cenário de 8 CPUs isso
compartilha parte dos recursos físicos. Não foi uma VM de nuvem.

Foi construída a imagem descartável `registro-ponto-carga50:20261119` a partir do
Dockerfile do projeto, com label `ponto.teste=carga50-20261119`. Ambiente com
`DEBUG=False`, WhiteNoise, modelos YuNet/SFace incluídos no build e PostgreSQL 17.
A imagem anterior `registro-ponto-web:latest` não foi substituída.

Aplicação e banco compartilharam `--cpuset-cpus=0,1`, `0,1,2,3` ou `0..7`, sem quota
individual que impedisse um deles de aproveitar CPU ociosa do outro. Os limites seguiram
os [controles de recursos do Docker](https://docs.docker.com/engine/containers/resource_constraints/).

| Orçamento nominal | Limite da aplicação | Limite do banco | Margem não alocada aos contêineres |
| --- | ---: | ---: | ---: |
| 2 GiB | 1.536 MiB | 256 MiB | 256 MiB |
| 4 GiB | 3.072 MiB | 512 MiB | 512 MiB |
| 8 GiB | 6.144 MiB | 1.024 MiB | 1.024 MiB |

Swap desativado nos contêineres. A margem não alocada é um orçamento para a VM, não uma
medição ou limitação do sistema operacional do host. Os limites não obrigam os processos
a consumir a memória reservada. O OpenCV usou os padrões da imagem; foram confirmadas
2, 4 e 8 threads nas respectivas configurações. Não foi aplicado ajuste de threads.

O banco de teste recebeu 50 contas fictícias e 9.000 batidas históricas de 30 dias.
Cada configuração executou:

1. GET de preparação do CSRF, fora da medição, e 50 logins reais simultâneos.
2. Três rajadas de 50 POSTs em `/bater_ponto/`, sem seguir o redirecionamento ao painel.
3. Uma rajada facial com os modelos frios e três aquecidas em `/ponto/camera/`.
4. Conferência das linhas gravadas após cada rajada. As batidas de hoje do banco fictício
   foram removidas entre rajadas, conservando a regra real de intervalo da aplicação.

Cookies e CSRF foram preservados por conta. O reconhecimento recebeu JPEG de 444 × 480,
com aproximadamente 48 KB, derivado da
[amostra pública do OpenCV](https://github.com/opencv/opencv/blob/master/samples/data/lena.jpg).
A mesma amostra e seu vetor foram associados diretamente às 50 contas fictícias para
medir processamento e persistência no fluxo pessoal. O motor extraiu e comparou o vetor
em cada requisição; não houve bypass de inferência. Esse preparo não exercita o cadastro
supervisionado nem a diferenciação de 50 rostos reais ou o terminal compartilhado.

CPU foi medida pela diferença do contador acumulado de cada contêiner; CPU e memória
foram amostradas aproximadamente a cada 200 ms pela API local do Docker. Rajadas curtas
produzem poucas amostras: os picos são observados, não máximos garantidos. Estatísticas
HTTP, integridade e medições estão nos
[dados completos](resultados/carga-50-2026-11-19.json).

## Limites da conclusão

A indicação de 4 vCPU / 4 GB é uma escolha de dimensionamento com margem, inferida dos
resultados. Uma vCPU de nuvem não equivale necessariamente a um núcleo deste host.
Antes de colocar a VM em produção, repetir o cenário escolhido nela, considerando rede,
HTTPS, tablets e latência do banco. Não foi aplicado um fator arbitrário de correção.

Não foram medidos PDFs e backups concorrentes, anos de histórico, pico prolongado,
vazamento de memória, precisão de reconhecimento com pessoas diferentes ou o tempo de
captura/iluminação das câmeras. Os 3 segundos da confirmação visual não fazem parte do
tempo HTTP. O ensaio aprovou as rajadas de gravação descritas, não uma carga ilimitada.

Uma preparação inicial com quotas separadas para banco e aplicação foi descartada por
não representar uma VM em que ambos compartilham CPU. Seus números não entram nas tabelas
nem no arquivo de resultados publicado.

## Descarte e isolamento

Foram removidos os contêineres `ponto-carga50-web` e `ponto-carga50-db`, o volume
`ponto-carga50-pg`, a rede `ponto-carga50-net`, a imagem temporária, seu estágio de build e
as imagens Python/PostgreSQL baixadas exclusivamente para o ensaio. Não foi usado prune
global. Os serviços e imagens preexistentes foram preservados; o banco do usuário e a
aplicação da porta 8000 não foram acessados pelo gerador.
