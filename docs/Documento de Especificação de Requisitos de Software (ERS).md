# Especificação de Requisitos de Software — ArchPath

## 1. Visão geral e escopo arquitetural

O ArchPath é um simulador pedagógico de backend que representa a jornada de um dado desde a captura de uma tecla até a saída simulada por uma interface de rede. A execução é sequencial e controlada por uma Máquina de Estados Finita (FSM); o cliente envia comandos por HTTP e recebe eventos por Server-Sent Events (SSE).

A primeira versão é single-user, mantém no máximo uma simulação ativa na memória de uma única instância/processo do serviço e destina-se a execução em localhost ou rede privada confiável. Não há persistência após reinício do servidor, suporte a múltiplas réplicas, tráfego de rede externo ou emulação física fiel.

## 2. Requisitos funcionais

**RF01 — Início da simulação:** `POST /api/simulacao/iniciar` deve receber `tecla_entrada` com exatamente uma letra maiúscula de `A` a `Z`, um algarismo de `0` a `9` ou espaço. A entrada representa o caractere lógico, não uma sequência física de teclas. Para a demonstração, o mapeamento associa esse caractere ao make code didático do conjunto 1 conforme a tabela do Apêndice A; o driver preserva o caractere lógico recebido, inclusive sua caixa, sem modelar Shift, outros modificadores, break codes, acentos, pontuação ou teclas de função. Opcionalmente, recebe `cenario_memoria`, com valores `normal` ou `page_fault`; a ausência equivale a `normal`. Entrada malformada ou fora do conjunto suportado retorna `400 Bad Request`. Se já houver execução ativa, retorna `409 Conflict` sem alterar ou descartar o contexto. Em OCIOSO, o sistema limpa recursos da execução anterior e cria novo contexto em RODANDO.

**RF02 — Eventos da simulação:** o backend deve publicar eventos JSON por `GET /api/simulacao/eventos` usando SSE (`Content-Type: text/event-stream`). Cada evento deve conter `sessao_id`, timestamp ISO 8601, `status_fsm`, módulo, componente, tipo do evento, ação executada e estado do dado. Eventos são ordenados por sequência dentro da sessão e identificados no campo SSE `id`. O serviço mantém em memória o histórico da sessão atual e da última sessão concluída para replay via `Last-Event-ID`; o histórico é descartado ao iniciar outra sessão e não sobrevive ao reinício do processo.

**RF03 — Controle pedagógico:** o sistema deve expor `POST /api/simulacao/pause`, `/resume` e `/step`. A unidade de avanço é uma transição completa de componente da jornada. `pause` solicitado durante RODANDO permite concluir a transição em curso e suspende antes da próxima. `step` só é aceito em PAUSADO, passa transitoriamente por AGUARDANDO_STEP, executa uma transição, publica o evento resultante e retorna a PAUSADO. A resposta HTTP de `step` ocorre após a transição. Comandos incompatíveis com o estado atual retornam `400 Bad Request`.

**RF04 — Nascimento do dado (I/O):** o sistema deve representar o fechamento do circuito do teclado, a variação de tensão, a geração de scancode pelo microcontrolador, a transmissão/decodificação na interface e o disparo de IRQ via APIC.

**RF05 — Processamento e tradução:** o sistema deve representar o atendimento da interrupção, o fetch do scancode pela CPU para registradores e a tradução pelo driver do sistema operacional para o caractere lógico correspondente.

**RF06 — Memória e Page Fault:** no cenário `normal`, o sistema deve representar a tradução de endereço virtual para físico e a alocação no buffer da RAM. No cenário `page_fault`, deve emitir uma exceção fatal antes da alocação, concluir a sessão com resultado de erro e não executar DMA nem rede. Nesta versão não há recuperação por swapping.

**RF07 — Transferência DMA:** o sistema deve representar a leitura do dado diretamente do buffer da RAM e seu encaminhamento ao barramento de expansão sem ciclos de CPU para essa transferência simulada.

**RF08 — Encapsulamento e saída de rede:** o sistema deve representar o percurso descendente pelas camadas lógicas de rede, a inclusão de cabeçalho UDP e IP, a formação de uma representação didática de quadro Ethernet pelo MAC, a fila da NIC e a conversão simulada de bits pelo PHY. UDP é o protocolo fixo da demonstração. Não há transmissão para rede externa nem exigência de cálculo bit-exato de frame ou CRC.

**RF09 — Consulta de estado:** `GET /api/simulacao/status` deve retornar os dados da sessão ativa. Quando não houver execução ativa, deve retornar `404 Not Found` com `estado_fsm: "OCIOSO"`. A conclusão normal ou fatal é comunicada pelo evento `FINALIZADO`; após sua publicação, os recursos são liberados e o serviço volta a OCIOSO.

## 3. Requisitos não funcionais

**RNF01 — Exclusividade e topologia:** deve haver no máximo uma execução ativa na única instância/processo suportado. A aquisição da sessão é atômica e comandos que alteram a FSM são serializados. Multi-processo/multi-instância não é suportado nesta versão.

**RNF02 — Desacoplamento:** o núcleo de simulação não deve depender de bibliotecas visuais; deve operar sobre estruturas de dados e publicar eventos por uma abstração independente do transporte.

**RNF03 — Ritmo de execução:** a velocidade de apresentação/animação pertence ao cliente. O frontend pode enfileirar eventos, mas não altera o ritmo lógico do motor.

**RNF04 — Espera de controle:** pausa e retomada devem aguardar por mecanismo bloqueante/sinalização, sem busy-wait.

**RNF05 — Contexto de acesso:** a primeira versão destina-se a localhost ou rede privada confiável e não define autenticação. A exposição em rede pública não está autorizada por esta especificação e requer decisão e controles de acesso próprios.

**RNF06 — Origem web:** a interface deve preferencialmente ser servida na mesma origem da API. Se forem usadas origens distintas no desenvolvimento, CORS deve permitir somente a origem explicitamente configurada do frontend; wildcard não é permitido.

**RNF07 — Ambiente reproduzível:** a aplicação local e os testes automatizados devem ser executáveis com Docker Compose. O backend deve usar um único processo/worker; Compose não deve introduzir banco de dados, broker ou serviços externos não requeridos pelo produto.

**RNF08 — TDD e regressão automatizada:** cada funcionalidade nova ou alterada deve seguir Red → Green → Refactor: criar primeiro o teste, executar e confirmar a falha por comportamento ainda não implementado, escrever a menor implementação que o faz passar e então executar a suíte completa de regressão. A suíte deve cobrir testes unitários e de integração da API/SSE, além dos testes automatizados do frontend, e deve poder ser executada em containers.

Não são definidos limites quantitativos de desempenho, disponibilidade, capacidade ou eficácia pedagógica nesta versão.

## 4. Regras de negócio

**RN01 — Integridade sequencial:** uma transição só pode ocorrer após a conclusão da transição precedente; não é permitido saltar componentes da jornada.

**RN02 — Proteção da sessão:** uma requisição de início durante uma sessão ativa recebe `409 Conflict` e não altera estado, dado, eventos ou lock da sessão existente.

**RN03 — Pausa:** a pausa solicitada durante uma transição é aplicada ao término dessa transição, antes de iniciar a próxima.

**RN04 — Passo:** cada chamada válida a `/step` executa exatamente uma transição de componente e retorna a FSM a PAUSADO.

**RN05 — Page Fault:** `page_fault` é cenário opcional de início. É fatal para a jornada e não inicia recuperação nem etapas subsequentes.

**RN06 — Finalização e limpeza:** ao concluir normalmente ou por erro fatal, o serviço publica o evento terminal, libera o lock e os recursos da execução e passa a OCIOSO. O evento da sessão concluída permanece no histórico em memória até o próximo início aceito.

**RN07 — Valores de rede:** valores de endereço e exemplos de frame/CRC são didáticos/ilustrativos. Não são configuráveis pelo usuário e não representam garantia de quadro válido para transmissão real.

## 5. Máquina de estados

| Estado atual | Comando/evento | Condição | Estado resultante | Resultado |
|---|---|---|---|---|
| OCIOSO | `iniciar` | Entrada válida | RODANDO | Cria sessão e inicia jornada. |
| OCIOSO | `iniciar` | Entrada inválida | OCIOSO | HTTP 400; nenhum contexto criado. |
| RODANDO | `iniciar` | Sessão ativa | RODANDO | HTTP 409; sessão existente não é alterada. |
| RODANDO | `pause` | Transição atual termina | PAUSADO | Suspende antes da próxima transição; HTTP 200. |
| PAUSADO | `resume` | Sessão ativa | RODANDO | Retoma execução; HTTP 200. |
| PAUSADO | `step` | Sessão ativa | AGUARDANDO_STEP → PAUSADO | Uma transição, evento publicado; HTTP 200 após conclusão. |
| RODANDO | `step` | — | RODANDO | HTTP 400; nenhuma ação. |
| PAUSADO | `pause` | — | PAUSADO | HTTP 400; nenhuma ação. |
| RODANDO | `resume` | — | RODANDO | HTTP 400; nenhuma ação. |
| OCIOSO | `pause`, `resume` ou `step` | Sem sessão ativa | OCIOSO | HTTP 400; nenhuma ação. |
| RODANDO ou AGUARDANDO_STEP | Page Fault | Cenário habilitado | FINALIZADO → OCIOSO | Evento terminal de erro, limpeza e liberação do lock. |
| RODANDO | Última transição concluída | Jornada normal | FINALIZADO → OCIOSO | Evento terminal de sucesso, limpeza e liberação do lock. |
| RODANDO ou AGUARDANDO_STEP | Erro interno irrecuperável | Falha não recuperável | FINALIZADO → OCIOSO | Evento terminal de erro, limpeza e liberação do lock. |

`AGUARDANDO_STEP` é transitório e pode ser observado por `GET status` durante a execução do passo. O evento da transição concluída informa o estado pós-transição (`PAUSADO`, `RODANDO` ou `FINALIZADO`), não o estado transitório de espera.

## 6. Critérios gerais de aceitação

1. A jornada normal percorre os componentes na ordem definida, sem saltos.
2. Cada evento é JSON, tem os campos obrigatórios, timestamp ISO 8601 e ID SSE crescente dentro da sessão.
3. `step` aceito em PAUSADO conclui exatamente uma transição completa e retorna a PAUSADO; `step` em outro estado é rejeitado.
4. `pause` não interrompe a transição em curso e impede a seguinte.
5. Início concorrente não altera a sessão ativa e responde 409.
6. Page Fault termina a sessão antes da alocação e não há eventos DMA ou rede depois dele.
7. Término normal e erro fatal publicam evento terminal antes de liberar recursos.
8. Reconexão com `Last-Event-ID` reproduz os eventos seguintes do histórico em memória; após reinício do processo não há replay persistente.
9. Entrada não suportada retorna 400; omissão de `cenario_memoria` inicia cenário normal.
10. A aplicação inicia pelo Docker Compose em localhost com frontend e backend, sem mais de um processo/worker de backend.
11. Um comando automatizado de testes via Docker Compose executa testes unitários e de integração do backend (incluindo API/SSE), testes do frontend e smoke tests ponta a ponta de browser com frontend/API reais, falhando se qualquer suíte falhar.
12. Para cada nova funcionalidade, o registro de desenvolvimento comprova que o teste foi executado primeiro e falhou pela ausência do comportamento requerido antes da implementação; a suíte de regressão passa após o código.
13. CI executa todas as suítes de regressão em containers em cada push/pull request; merge é bloqueado se alguma falhar ou for omitida.

## Apêndice A — Mapeamento didático de scancode

Usa-se scancode set 1, make code, para manter uma tabela determinística entre a entrada lógica e o valor didático apresentado nos eventos. A entrada textual é o caractere lógico final: por exemplo, `A` associa-se ao make code da tecla A e o driver retorna `A`, sem simular a tecla Shift. Este mapeamento é uma abstração pedagógica; não modela relatórios HID USB, modificadores, break codes, layout físico completo ou transmissão elétrica.

| Entrada | Scancode | Entrada | Scancode | Entrada | Scancode |
|---|---:|---|---:|---|---:|
| A | `0x1E` | J | `0x24` | S | `0x1F` |
| B | `0x30` | K | `0x25` | T | `0x14` |
| C | `0x2E` | L | `0x26` | U | `0x16` |
| D | `0x20` | M | `0x32` | V | `0x2F` |
| E | `0x12` | N | `0x31` | W | `0x11` |
| F | `0x21` | O | `0x18` | X | `0x2D` |
| G | `0x22` | P | `0x19` | Y | `0x15` |
| H | `0x23` | Q | `0x10` | Z | `0x2C` |
| I | `0x17` | R | `0x13` | Espaço | `0x39` |

| Entrada | Scancode |
|---|---:|
| 1 | `0x02` |
| 2 | `0x03` |
| 3 | `0x04` |
| 4 | `0x05` |
| 5 | `0x06` |
| 6 | `0x07` |
| 7 | `0x08` |
| 8 | `0x09` |
| 9 | `0x0A` |
| 0 | `0x0B` |
