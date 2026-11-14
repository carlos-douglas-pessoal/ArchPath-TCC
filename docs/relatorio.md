# Relatório de Auditoria Documental — ArchPath

**Data da análise:** 16 de outubro de 2026
**Natureza:** auditoria documental; não avalia código nem comprova comportamento implementado.

## A. Resumo executivo

O ArchPath é um simulador pedagógico de backend cujo propósito é tornar observável a jornada de um dado desde a captura de uma tecla até a transmissão simulada pela interface de rede. O ERS, o PRD e os diagramas descrevem um fluxo compreensível de I/O, CPU, sistema operacional, memória, DMA e rede, controlado por uma máquina de estados finita e acompanhado por eventos.

O propósito e o percurso principal estão claros. O PRD também delimita o escopo, registra decisões de produto e fornece critérios de aceitação. A documentação, porém, ainda não está completamente consolidada para implementação ponta a ponta: existem divergências entre o transporte SSE definido pelo PRD e o WebSocket descrito no catálogo de eventos, diferenças de semântica de estados e de passo, e ambiguidades sobre terminalidade e limpeza de sessão. O Page Fault fatal é uma decisão registrada no PRD, mas não está alinhada com o ERS e com o exemplo de evento que menciona swapping.

Não há evidência documental para classificar algum problema como P0. Há achados P1 que devem ser resolvidos antes da implementação das interfaces afetadas e achados P2 relacionados a validação, rastreabilidade, qualidade e cenários de erro. O fluxo pedagógico básico pode orientar uma implementação inicial se o PRD for tratado como fonte normativa, mas a documentação precisa ser harmonizada antes da integração do cliente, API e emissor de eventos.

**Veredito:** **Aprovada com ressalvas**, condicionada à resolução das divergências P1 antes da implementação das funcionalidades afetadas. Esta avaliação não afirma que o sistema foi implementado ou testado.

## B. Entendimento do produto

### Propósito e problema

O produto procura reduzir a abstração do funcionamento interno de um computador para estudantes de arquitetura de computadores e sistemas operacionais. A simulação transforma conceitos em uma sequência de componentes e mudanças observáveis, controlável pelo aluno ou por um demonstrador.

### Públicos e necessidades

- **Aluno:** acompanhar a ordem do processamento e compreender as transformações do dado.
- **Professor/demonstrador:** pausar e avançar a execução para explicar etapas.
- **Cliente frontend:** receber eventos estruturados e representar visualmente a jornada sem controlar o motor.

Os dois primeiros perfis estão declarados no PRD; a necessidade do cliente frontend é uma necessidade técnica de integração, não um perfil de usuário final independente.

### Escopo funcional compreendido

O percurso esperado é:

1. Captura de tecla, variação de tensão e geração de scancode.
2. Recepção/decodificação de I/O, passagem pelo chipset e IRQ via APIC.
3. Atendimento da interrupção e fetch do dado pela CPU para registradores.
4. Tradução do scancode em caractere lógico pelo driver do sistema operacional.
5. Tradução de endereço e alocação em buffer na RAM, com cenário opcional de Page Fault.
6. Transferência simulada por DMA ao barramento de expansão.
7. Encapsulamento lógico pela pilha de rede e formação de quadro Ethernet.
8. Conversão simulada pelo PHY e saída física.

Ficam fora do escopo declarado a emulação física fiel, tráfego de rede externo, concorrência multiusuário e ajuste da velocidade lógica pelo frontend. O servidor mantém uma sessão global em memória.

### Clareza do propósito e alinhamento

O propósito, o caminho principal e a relação entre requisitos e objetivos pedagógicos são suficientemente claros. Não há requisito claramente alheio ao produto, embora alguns detalhes de hardware (por exemplo, valores de registradores, endereços de rede e CRC do quadro) precisem ser justificados como valores didáticos fixos ou removidos dos exemplos se não forem parte do comportamento esperado.

O objetivo de apoiar a aprendizagem não possui critério de sucesso educacional mensurável. Isso não invalida os requisitos de simulação, mas significa que a documentação permite validar o comportamento técnico e não comprovar, por si só, que o produto melhora a aprendizagem.

## C. Documentos analisados

### Fontes principais

- [ERS](./Documento%20de%20Especificação%20de%20Requisitos%20de%20Software%20(ERS).md) — visão arquitetural, RF01–RF08, RNF01–RNF04 e RN01–RN02. O documento não apresenta número de versão.
- [PRD](./prd.md) — visão de produto, escopo, RF01–RF09, RN01–RN07, RNF01–RNF06, contratos propostos, eventos, critérios de aceitação e pontos em aberto.
- [Diagrama de componentes](./modelagem-plantuml/1-Diagrama%20de%20Componentes.txt).
- [Diagrama de classes — Módulo 1, I/O e nascimento do dado](./modelagem-plantuml/2-Diagrama%20de%20Classes%20Módulo%201%20(I%20e%20O%20e%20Nascimento%20do%20Dado).txt).
- [Diagrama de classes — Módulo 2, CPU e tradução](./modelagem-plantuml/2-Diagrama%20de%20Classes%20Módulo%202%20(CPU%20e%20Tradução).txt).
- [Diagrama de classes — Módulo 3, memória e sistema operacional](./modelagem-plantuml/2-Diagrama%20de%20Classes%20Módulo%203%20(Memória%20e%20SO).txt).
- [Diagrama de classes — Módulo 4, rede e encapsulamento OSI](./modelagem-plantuml/2-Diagrama%20de%20Classes%20Módulo%204%20(Rede%20e%20Encapsulamento%20OSI).txt).
- [Diagrama de atividades — jornada do dado sob a FSM](./modelagem-plantuml/3-Diagrama%20de%20Atividades%20-%20A%20Jornada%20do%20Dado%20sob%20o%20FSM.txt).
- [Diagrama de atividades — pausa e retomada](./modelagem-plantuml/3-Diagrama%20de%20Atividades%20-%20O%20Fluxo%20de%20Controle%20(Pause%20e%20Resume).txt).

### Artefatos relacionados considerados

O PRD também referencia uma [especificação OpenAPI](./documentos-extras/1-Especificação%20OpenAPI%20(Swagger)%20da%20API%20REST.txt), o [catálogo de eventos SSE e schemas](./documentos-extras/2-Catálogo%20de%20Eventos%20SSE%20e%20Schemas%20JSON.txt) e a [arquitetura de erros e concorrência](./documentos-extras/3-Arquitetura%20de%20Tratamento%20de%20Erros%20e%20Concorrência.txt). Foram considerados para explicar as divergências já assinaladas no PRD; o foco desta auditoria permanece ERS, PRD e diagramas.

### Limitações

- A análise é documental; não inclui inspeção de código, protótipo, execução ou testes.
- O ERS é conciso e não contém regras de transição completas, cenários de erro detalhados ou contratos de API completos.
- Os diagramas são modelos conceituais. Nomes de classes e exemplos não devem ser interpretados automaticamente como contratos de produção.
- Não foram fornecidos metas quantitativas, estudo de usuários ou critérios de aprendizagem.

## D. Inconsistências entre documentos

| ID | Prioridade | Fontes e evidência | Conflito e consequência | Decisão/ação necessária |
|---|---|---|---|---|
| A-01 | P1 | ERS RF02 permite WebSocket ou SSE; PRD §§1, 9 e 11 adota SSE; catálogo referenciado pelo PRD descreve WebSocket. | A implementação do cliente e do backend pode selecionar transportes incompatíveis. Também não se sabe se o catálogo é um schema independente de transporte ou uma especificação WebSocket efetiva. | Confirmar SSE como contrato normativo (a escolha atual do PRD) e atualizar catálogo/OpenAPI/diagrama de componentes para remover WebSocket, ou reabrir a decisão de produto formalmente. Definir rota, MIME e reconexão do SSE. |
| A-02 | P1 | ERS RF03 diz que a FSM retém a simulação no componente atual; diagrama de pausa/resume descreve espera no loop entre passos e `/step` volta a PAUSADO após avançar; PRD §7 diz que `AGUARDANDO_STEP` é um estado distinto e que `pause` pode concluir o componente atual. | “Componente”, “passo” e “etapa” podem representar unidades diferentes. A transição imediata ou diferida de `pause` e o estado observado durante `/step` não estão uniformemente definidos. Testes e animações podem contar quantidades diferentes de passos. | Definir uma unidade de avanço (recomenda-se uma transição de componente, conforme especificação de controle) e documentar uma única tabela de transições, efeitos e estados reportados; alinhar ERS e diagrama. |
| A-03 | P1 | ERS RF06 pede Page Fault antes da alocação, sem declarar resultado terminal; PRD §§4–7 e §10 define cenário fatal; exemplo de evento do catálogo relata `PAUSADO` e “acionando rotina de swapping”. | A mesma ocorrência pode significar abortar a jornada ou suspender e recuperar. Se fatal, o exemplo de swapping contradiz o resultado; se recuperável, os critérios atuais encerram cedo demais. | Manter como decisão de produto já registrada no PRD (fatal) somente após validação do responsável; então corrigir ERS, catálogo e evento para `FINALIZADO`, sem prometer recuperação. Se a intenção original era recuperação, rever PRD e critérios em vez de implementar a decisão silenciosamente. |
| A-04 | P1 | PRD §§7, 9 e 11 declara `OCIOSO`, `RODANDO`, `PAUSADO`, `AGUARDANDO_STEP` e `FINALIZADO`; schema do catálogo original lista apenas `RODANDO`, `PAUSADO`, `AGUARDANDO_STEP`; endpoint de status retorna `404` e `OCIOSO` sem simulação. | Os estados não têm enumeração comum nem regra uniforme para status HTTP versus estado no corpo. Após terminar, não está definido se o contexto permanece consultável, é imediatamente liberado ou transita a OCIOSO antes da próxima sessão. | Consolidar enumeração de estados e ciclo de vida, separando código HTTP de estado de domínio. Atualizar schema e contrato de status com pós-condições de sucesso e falha. |
| A-05 | P1 | ERS RF01 descreve limpar resíduos de execuções anteriores; OpenAPI referido no PRD menciona descartar contexto “zumbi”; regra de exclusividade ERS RN02 e PRD RN02 proíbem substituir uma simulação ativa. | “Limpar” pode ser entendido como reset forçado ou como limpeza apenas depois do término. A descrição do OpenAPI entra em conflito se tratar qualquer contexto residual como descartável. | Fixar a precedência: sessão ativa nunca é descartada; início ativo retorna 409; limpeza só é permitida quando o serviço está ocioso/terminal. Explicitar a recuperação de processo interrompido, se necessária. |
| A-06 | P2 | Diagrama de componentes e diagramas de classe representam emissores por módulo; PRD §9 agrega um emissor comum. O catálogo usa campos detalhados; ERS RF02 pede timestamp, componente e transformação. | Os campos mínimos diferem; o objeto `estado_do_dado` é genérico e nenhum identificador de sequência/evento é definido. Reconexão de cliente pode perder ou duplicar eventos sem estratégia documentada. | Estabelecer um schema normativo único e documentar ordenação, identificação, política de reconexão e se existe ou não replay. Não adicionar campos obrigatórios sem necessidade validada. |
| A-07 | P2 | RF02 do ERS permite dois transportes; PRD adotou SSE, mas sua tabela de eventos contém rota proposta não coberta pelo OpenAPI referido em §9. | Uma integração pode considerar `/api/simulacao/eventos` aprovado, embora o próprio PRD o classifique como proposta. | Incorporar a rota SSE ao contrato formal da API e identificar claramente quais elementos do PRD ainda são propostas. |
| A-08 | P2 | PRD §9 descreve `200` para início, controle; `400`, `404` e `409` em estados específicos, enquanto a modelagem da jornada apresenta fluxo normal sem tratar respostas de comandos inválidos ou falhas de execução. | Casos de comando válido sintaticamente, mas incompatível com a FSM, têm resposta em texto no OpenAPI relacionado, porém não há schema de erro estável nem comportamento pós-falha do motor. | Formalizar modelo de erro de API, estado resultante, possibilidade de retentativa e evento de erro correspondente; manter comportamento conforme o escopo single-user. |
| A-09 | P2 | Diagramas de classes de rede mostram TCP/UDP, IP, MAC, Ethernet, fila e PHY; PRD §4 exclui tráfego externo e §5 descreve valores fixos. | Exemplos de cabeçalhos, FCS/CRC e sinal podem ser lidos como exigência de cálculos reais, embora o objetivo seja simulação pedagógica e detalhes/defaults não estejam normatizados. | Especificar quais campos são valores ilustrativos e quais transformações devem ser calculadas. Evitar usar exemplos sem declarar se são normativos ou demonstrativos. |

## E. Problemas nos requisitos

### Achados priorizados

#### A-01 — Transporte de eventos sem contrato único — P1

- **Categoria:** arquitetura/integração.
- **Origem:** ERS RF02; PRD §§1, 9 e 11; diagrama de componentes; catálogo de eventos relacionado.
- **Evidência:** ERS oferece “WebSocket ou Server-Sent Events”; PRD escolhe SSE; catálogo é intitulado e descrito como WebSocket.
- **Problema/consequência:** front e backend podem implementar protocolos diferentes. SSE é apropriado ao fluxo unidirecional descrito, mas a escolha deve estar refletida em todos os artefatos normativos.
- **Correção sugerida:** declarar um único transporte e atualizar desenho, schema e API. O PRD já registra SSE como decisão; portanto, alinhar os demais documentos a essa decisão aprovada.
- **Critério de resolução:** o PRD, ERS, diagrama de componentes, API e catálogo nomeiam o mesmo canal e descrevem conexão, formato, fechamento e reconexão de forma compatível.

#### A-02 — Semântica de pausa e avanço ambígua — P1

- **Categoria:** FSM/comportamento/testabilidade.
- **Origem:** ERS RF03; diagrama de atividades “O Fluxo de Controle (Pause e Resume)”; PRD §§7, 9 e 10.
- **Evidência:** o ERS retém no componente atual; o diagrama alterna execução e espera e especifica passo unitário; o PRD introduz `AGUARDANDO_STEP` e diz que pause pode deixar o componente atual terminar.
- **Problema/consequência:** não está definido se “um passo” equivale a um componente, a uma etapa macro das oito, ou a uma transição interna. A resposta do comando pode acontecer antes/depois da conclusão da unidade e isso altera o número e a ordem de eventos.
- **Redação proposta (submeter ao responsável):** “A unidade de `step` é uma transição de componente da jornada. O comando só é aceito em `PAUSADO`; a FSM passa a `AGUARDANDO_STEP`, executa uma única transição completa, publica o evento resultante e retorna a `PAUSADO`. `pause` solicitado em `RODANDO` permite concluir a transição em curso e impede o início da seguinte.”
- **Impacto:** ERS RF03, diagrama de controle, schema/status, endpoint e critérios AC4–AC5/AC12.
- **Critério de resolução:** tabela de transições aprovada e testes com contagem de eventos comprovam exatamente uma transição por step.

#### A-03 — Page Fault fatal versus recuperação — P1

- **Categoria:** regra de negócio/fluxo excepcional.
- **Origem:** ERS RF06; PRD §§4–7, §9, §10 e §11; exemplo Page Fault do catálogo.
- **Evidência:** ERS só exige exceção antes da alocação; PRD escolhe encerramento fatal; exemplo do catálogo relata swapping, interrupção 14 e estado PAUSADO.
- **Problema/consequência:** altera o resultado da jornada, sua terminalidade, eventos seguintes e possibilidade de nova sessão. Em material pedagógico, também muda o conceito ensinado: falha de tradução pode envolver tratamento/recuperação e não necessariamente significa estouro fatal.
- **Estado da decisão:** PRD registra fatal, mas ERS e exemplo continuam desalinhados. A decisão precisa ser validada e propagada; este relatório não eleva exemplos à regra.
- **Redação proposta, se fatal for confirmado:** “No cenário `page_fault`, a tabela de páginas emite uma falha de tradução antes da alocação; a simulação registra o evento terminal `FINALIZADO` com resultado de erro e não executa DMA ou rede. Não ocorre swapping nem retomada nesta versão.”
- **Impacto:** ERS RF06, exemplo/schema do evento, estados, limpeza de sessão e critérios AC7/AC12.
- **Critério de resolução:** os documentos descrevem o mesmo resultado fatal ou recuperável, e teste valida a ausência/presença das etapas seguintes.

#### A-04 — Ciclo de vida, estado terminal e status — P1

- **Categoria:** contrato de domínio/API.
- **Origem:** PRD §§7, 9 e 11; endpoint de status no OpenAPI relacionado; schema do catálogo.
- **Problema/consequência:** `FINALIZADO` e `OCIOSO` aparecem em locais diferentes; não há contrato de retenção do último status, liberação do lock, nem instante em que a sessão passa a OCIOSO. O status `404` pode ser interpretado como falha de transporte em vez de ausência normal de sessão.
- **Correção sugerida:** definir o ciclo `OCIOSO → RODANDO ↔ PAUSADO → FINALIZADO → OCIOSO` (com `AGUARDANDO_STEP` temporário) e especificar o resultado de `GET status` em FINALIZADO. Essa proposta requer aprovação: estado terminal reportável por período limitado ou liberação imediata.
- **Critério de resolução:** estados e transições aparecem iguais no PRD, schema, API e diagrama; status HTTP e status FSM são campos separados e definidos.

#### A-05 — Inicialização, lock e descarte de sessão — P1

- **Categoria:** integridade/concorrência.
- **Origem:** ERS RF01/RNF01/RN02; PRD RF01/RN02/RNF06/§9.
- **Problema/consequência:** inicialização deve limpar dados antigos, mas nunca sobrescrever contexto ativo. Embora o PRD registre a precedência, o ERS e a descrição de “contexto zumbi” podem levar à implementação de reset destrutivo. A expressão “lock global” também não esclarece se a exclusão mútua cobre um único processo ou uma implantação com múltiplos workers/instâncias.
- **Redação proposta:** “A aquisição da sessão é atômica. Se o estado não for OCIOSO, `iniciar` retorna 409 sem alterar o contexto. A inicialização limpa e recria os recursos somente quando o serviço está OCIOSO. A garantia é por instância única do serviço; implantação multi-processo/multi-instância está fora do escopo, a menos que especificada.”
- **Decisão pendente:** confirmar implantação de instância única ou definir mecanismo compartilhado de lock antes de escalar para múltiplos workers.
- **Critério de resolução:** ERS/PRD/API concordam na precedência; teste concorrente demonstra exatamente uma criação de sessão e nenhuma mutação por requisição rejeitada.

#### A-06 — Campos do evento e consistência entre status e progresso — P2

- **Categoria:** contrato de dados/observabilidade.
- **Origem:** ERS RF02; PRD RF02 e §9; schema e exemplos de eventos relacionados; diagramas de classe.
- **Problema/consequência:** o ERS pede componente e transformação; o catálogo descreve módulo, componente, ação e estado do dado. Falta indicar se cada evento é emitido antes ou depois da transição, se estado representa “antes/depois”, e como diferenciar eventos em retomada ou reconexão.
- **Correção sugerida:** definir semântica de snapshot pós-transição, timestamp, campos obrigatórios/opcionais e sequência ordenada. Para reconexão, escolher entre não garantir replay ou introduzir mecanismo de replay; esta última não deve ser assumida sem necessidade.
- **Critério de resolução:** um schema versionado e exemplos de eventos adjacentes cobrem início, execução, pausa, step, erro e término.

#### A-07 — Entradas e validação insuficientemente especificadas — P2

- **Categoria:** validação/entrada.
- **Origem:** ERS RF01/RF06; PRD tabela de API e §11; OpenAPI relacionado.
- **Problema/consequência:** “caractere” não informa se se aceitam espaços, caracteres multibyte, teclas de função ou string com mais de um caractere. `cenario_memoria` tem valores citados, mas o padrão quando ausente é apenas recomendado pelo PRD. Falhas de validação seriam implementadas de formas diferentes.
- **Correção sugerida:** definir limites e conjunto de entradas suportadas pelo simulador de teclado, regras de normalização e valor padrão explícito para `cenario_memoria` (o PRD recomenda `normal`).
- **Critério de resolução:** o schema de entrada inclui tipos, enum/default e limites; cenários válidos e inválidos têm respostas documentadas.

#### A-08 — Requisitos não funcionais e sucesso do produto pouco verificáveis — P2

- **Categoria:** qualidade/validação do produto.
- **Origem:** ERS RNF03/RNF04; PRD §§2, 8 e 10.
- **Problema/consequência:** “baseado exclusivamente no tempo de processamento lógico” não define uma medida de desempenho; não existem metas numéricas de latência, throughput, disponibilidade ou capacidade. Objetivos de aprendizagem não têm método ou indicador de avaliação. Isso impede afirmar desempenho ou efetividade educacional, embora não impeça validar o percurso funcional.
- **Correção sugerida:** responsáveis pelo produto devem decidir se são necessárias metas quantitativas de API/fluxo e como avaliar o objetivo educacional. Não atribuir números sem contexto de uso.
- **Critério de resolução:** requisitos mensuráveis são definidos quando necessários, ou a ausência é formalmente aceita para a primeira versão.

#### A-09 — Algoritmos/detalhes didáticos exemplificados sem limite normativo — P2

- **Categoria:** domínio/modelagem.
- **Origem:** diagramas de módulos 1–4; PRD §§5 e 9; catálogo de eventos relacionado.
- **Problema/consequência:** os diagramas nomeiam mapa ABNT2, registrador EAX, endereços, MAC broadcast, preâmbulo, tipo Ethernet e FCS/CRC, mas nem todos são fixados como valores de demonstração ou cálculos obrigatórios. A documentação não deve fazer leitores tratarem dados ilustrativos como valores técnicos universais.
- **Correção sugerida:** marcar cada valor como constante pedagógica/exemplo ou especificar a transformação que deve ser calculada. Definir explicitamente se os valores de CRC e campos de Ethernet são simulados ou apenas narrativos.
- **Critério de resolução:** exemplos são rotulados e os critérios de aceitação exigem apenas propriedades que o produto realmente promete.

### Avaliação geral de qualidade dos requisitos

- **Clareza:** boa para o propósito e jornada; parcial para estados excepcionais, unidade de passo e protocolos.
- **Completude:** suficiente para entender o fluxo nominal; incompleta para entrada, término, falhas e reconexão.
- **Consistência:** há conflitos apontados em D; o PRD reconhece parte deles, mas documentos vinculados ainda precisam ser alinhados.
- **Necessidade/alinhamento:** RFs e regras centrais apoiam a proposta pedagógica; detalhes de campos de rede precisam de delimitação didática.
- **Viabilidade:** plausível para um simulador didático de backend, mas deployment e event delivery não estão suficientemente definidos para prometer garantias além de processo único.
- **Verificabilidade:** critérios AC1–AC12 ajudam; critérios de entrada, transição, finalização e contrato ainda precisam de precisão.
- **Rastreabilidade:** IDs RF/RNF/RN existem no ERS e PRD, mas não há matriz oficial objetivo-requisito-teste; esta auditoria fornece uma visão.
- **Atomicidade:** vários requisitos agrupam múltiplos comportamentos, especialmente RF04, RF06 e RF08; podem ser decompostos em testes por etapa sem necessariamente alterar o escopo.

## F. Requisitos ausentes e lacunas

| Lacuna | Por que importa / risco | Decisão ou proposta necessária |
|---|---|---|
| Tabela normativa completa de transições FSM | Evita estados sem saída e divergência entre API, worker e frontend. | Definir estado atual, comando/condição, novo estado, resposta HTTP, evento emitido e efeito sobre lock/contexto (ver tabela abaixo). |
| Resultado e retenção após finalização | Determina resposta do status, liberação do lock e quando outro início é permitido. | Decidir se `FINALIZADO` é observável por um período ou se a sessão fica imediatamente `OCIOSO`; não inferir política de retenção. |
| Comportamento após exceção fatal e erros internos | PRD cobre Page Fault, mas não falha inesperada do motor/emissor. | Definir evento terminal, resposta/status observável, limpeza e permissão para iniciar nova simulação. |
| Transporte e reconexão SSE | O transporte é escolhido, mas rota e reconexão não estão contratadas. | Incorporar endpoint SSE ao contrato; declarar se reconexão é best-effort ou replay. |
| Ordenação/duplicidade de eventos | Cliente precisa reconstruir animação/histórico; reconnect pode criar lacunas. | Especificar ordenação por conexão e comportamento em desconexão, sem exigir replay se fora do escopo. |
| Validação de entrada | “Caractere” é insuficiente para definir dados aceitos e testes negativos. | Fixar conjunto de teclas suportado, tamanho, codificação, valores default e erros de validação. |
| Limites didáticos de memória | Page Fault por “estouro” e endereço solicitado não têm limites ou política de cálculo definidos. | Especificar regra determinística de geração da falha e quais dados aparecem no evento; manter apenas o que é necessário à aprendizagem. |
| Semântica de camadas e valores da rede | Diagrama mostra várias camadas, enquanto nomes/protocolos e campos de exemplo não são todos normativos. | Declarar ordem e transformação exigidas; decidir se valores fixos são constantes ou exemplos, particularmente TCP/UDP e campos do frame. |
| Segurança de acesso/uso | Não há autenticação/autorização nem restrição de origem documentada. Pode ser aceitável em ferramenta local, mas perigoso se exposta em rede. | Definir contexto operacional previsto (local, rede confiável, pública) e controles proporcionais; não tratar como obrigação sem esclarecer o deployment. |
| Avaliação da aprendizagem | O objetivo pedagógico é central, mas os critérios atuais são de comportamento técnico. | Se sucesso educacional for requisito de produto, definir com responsáveis método/indicador de avaliação; senão, deixar explicitamente fora dos critérios da versão. |
| Rastreabilidade para teste | ACs cobrem jornada, mas não há ligação sistemática por requisito nem testes de estado/erros. | Aprovar matriz de rastreabilidade e criar testes para os requisitos essenciais e negativos. |

### Tabela de transições proposta para aprovação

Esta tabela é uma proposta de consolidação derivada dos contratos já descritos; as linhas marcadas **pendente** não devem ser consideradas decisão aprovada.

| Estado atual | Comando/evento | Condição | Estado resultante | Efeito/resposta |
|---|---|---|---|---|
| OCIOSO | `iniciar` | Entrada válida e lock adquirido | RODANDO | Criar estado inicial; responder 200. |
| OCIOSO | `iniciar` | Entrada inválida/ausente | OCIOSO | Não criar sessão; responder 400. |
| RODANDO | `iniciar` | Sessão existente | RODANDO | Não alterar contexto; responder 409. |
| RODANDO | `pause` | Uma transição pode terminar | PAUSADO | Suspender antes da próxima transição; responder 200 conforme contrato a definir. |
| PAUSADO | `resume` | Sessão ainda ativa | RODANDO | Liberar execução contínua; responder 200. |
| RODANDO | `resume` | — | RODANDO | Rejeitar repetição com 400, conforme API relacionada. |
| PAUSADO | `step` | — | AGUARDANDO_STEP | Autorizar exatamente uma unidade de avanço; resposta síncrona/assíncrona ainda precisa ser fixada. |
| AGUARDANDO_STEP | Transição concluída | Jornada não terminou | PAUSADO | Publicar evento e reter antes da próxima unidade. |
| PAUSADO | `step` | Ainda não especificado se uma etapa terminal pode ser avançada | PENDENTE | Definir efeito e resposta. |
| RODANDO ou AGUARDANDO_STEP | Page Fault habilitado | Falha ocorre antes da alocação | FINALIZADO (se decisão fatal confirmada) | Publicar erro terminal; liberar lock/recursos conforme política definida. |
| RODANDO | Última etapa concluída | Término normal | FINALIZADO | Publicar conclusão; definir retenção/status e liberação de recursos. |
| FINALIZADO | Novo `iniciar` | Recursos liberados e estado ocioso | OCIOSO → RODANDO | A relação temporal entre FINALIZADO/OCIOSO precisa ser definida. |
| OCIOSO | `pause`, `resume` ou `step` | Sem sessão | OCIOSO | API relacionada indica erro 400 para comandos incompatíveis; confirmar corpo padrão. |
| Qualquer estado ativo | Falha interna | — | PENDENTE | Definir evento, estado terminal e limpeza. |

## G. Riscos de implementação e evolução

| Risco | Cenário desencadeador | Consequência | Probabilidade qualitativa | Prevenção |
|---|---|---|---|---|
| Cliente e servidor usam protocolos distintos | Frontend implementa WebSocket com base no catálogo; backend segue SSE do PRD. | Integração bloqueada e retrabalho. | Alta enquanto os documentos divergirem. | Alinhar o catálogo/diagrama/OpenAPI antes do desenvolvimento do canal. |
| Passo avança quantidade diferente de componentes | Um desenvolvedor interpreta step como etapa macro; outro como transição individual. | Animações e testes apresentam comportamento incompatível; aluno perde controle didático. | Alta dada a terminologia atual. | Aprovar unidade e tabela FSM; testar quantidade de eventos por step. |
| Exceção de memória produz jornada inconsistente | Exemplo emite PAUSADO e swapping enquanto PRD interrompe fatalmente. | DMA/rede podem continuar em uma implementação e cessar em outra. | Média-alta para o cenário opcional. | Alinhar regra, evento terminal e critério de aceitação. |
| Início remove contexto em uso | Implementação interpreta “limpar resíduos/zumbi” como reset mesmo com sessão ativa. | Perda do estado do aluno e violação do single-user. | Média, mitigada pelo PRD, mas texto de origem conflita. | Repetir regra de 409 em ERS/OpenAPI e cobrir com teste concorrente. |
| Sessão fica bloqueada após erro/queda | Processo mantém lock ou estado em memória após exceção/cliente desconectado. | Não é possível iniciar outra simulação; recurso aparenta ocupado. | Média; política de falha e timeout não está definida. | Definir limpeza/finalização e alcance do lock; distinguir desconexão do cliente de término da simulação. |
| Eventos perdidos/duplicados após reconexão | Cliente SSE desconecta e reabre fluxo sem regra de replay. | Estado visual diverge do estado real do motor. | Média, especialmente em recarga de página. | Definir status como mecanismo de ressincronização ou política de replay; testar desconexão. |
| Bloqueio não protege múltiplas instâncias | Serviço é executado com múltiplos workers/replicas, cada qual com lock local. | Mais de uma sessão global efetiva e status divergente. | Baixa se implantação for estritamente single-process; desconhecida sem deployment definido. | Declarar topologia suportada ou escolher coordenação compartilhada antes de escalar. |
| Valores ilustrativos viram regra técnica | Implementadores reproduzem MAC/CRC/registrador de exemplo como valor obrigatório, ou tentam emular detalhes não prometidos. | Complexidade e inconsistência didática; retrabalho em mudanças. | Média. | Rotular exemplos versus requisitos e delimitar fidelidade da simulação. |
| Requisito de “desempenho” não é validável | RNF03 é interpretado como promessa de velocidade sem métrica. | Discussão subjetiva de conclusão e otimização prematura. | Média. | Decidir se há meta de desempenho; caso haja, defini-la com condições e medição. |
| Objetivo pedagógico não é avaliado | Produto é aceito apenas pela presença de eventos, sem validar compreensão do usuário. | Sucesso técnico pode não corresponder à proposta educacional. | Média; depende do objetivo do projeto. | Acordar se validação educacional é requisito desta versão ou trabalho posterior. |

## H. Matriz de rastreabilidade

As associações entre objetivos descritivos e requisitos abaixo são inferidas a partir do texto do PRD. Os nomes dos objetivos são descritivos, não novos identificadores de requisito.

| Objetivo do produto | Requisitos relacionados | Regras relacionadas | Documentos relacionados | Critérios de aceitação | Lacuna identificada |
|---|---|---|---|---|---|
| Tornar visível a jornada do dado | RF02, RF04–RF08 (PRD); RF02, RF04–RF08 (ERS) | RN01 (integridade sequencial) | ERS §§1–2; PRD §§2, 5–6; diagramas de módulos 1–4 e jornada FSM | AC1, AC3, AC6–AC9, AC12 | Definição do que cada evento representa, snapshot antes/depois e valores ilustrativos (A-06, A-09). |
| Permitir exploração pedagógica controlada | RF03 (PRD/ERS) | RN03–RN04 (PRD) | ERS RF03; PRD §§5, 7, 9–10; diagrama de pause/resume | AC4–AC5 | Unidade de step, momento de pausa e transições de estados (A-02). |
| Demonstrar alocação e exceção de memória | RF06 (PRD/ERS) | RN05 (PRD) | ERS RF06; PRD §§4–7, 10–11; diagrama Módulo 3 | AC7 | Falha fatal versus swapping; limites de memória não especificados (A-03 e lacunas em F). |
| Mostrar transferência direta por DMA | RF07 (PRD/ERS) | RN01 (ordem) | ERS RF07; PRD §§5–6, 10; diagramas Módulos 3–4 | AC8 | “Sem ciclos de CPU” é propriedade da simulação; não há modelo detalhado de arbitragem ou contenda, o que parece aceitável fora do escopo. |
| Demonstrar encapsulamento e saída de rede | RF08 (PRD/ERS) | RN01, RN06 (PRD) | ERS RF08; PRD §§4–6, 10–11; diagrama Módulo 4 | AC9 | Valores e algoritmos de headers/frame são didáticos ou normativos? (A-09). |
| Manter controle exclusivo e integridade da sessão | RF01 (PRD/ERS) | RN02, RN07 (PRD); RN02 (ERS) | ERS RF01/RNF01/RN02; PRD §§6–9, 10–11; diagrama de componentes; arquitetura de erros/concorrência | AC1–AC2, AC11 | Ciclo terminal/ocioso, alcance do lock e sessão zumbi (A-04, A-05). |
| Desacoplar motor e cliente | RF02–RF03 | RNF02–RNF06 | ERS RNF02–RNF04; PRD §§8–9; diagrama de componentes | AC1, AC10, AC12 | Transporte divergente, schema, replay/reconexão SSE (A-01, A-06, A-07). |
| Apoiar aprendizagem de estudantes | RF04–RF08 (inferência) | RN01, RN03–RN06 (inferência) | PRD §§2–5; diagramas de jornada e módulos | AC3–AC10 | Não há critério/medição de aprendizagem; relação é objetivo de produto, não requisito educacional verificável. |

### Cobertura identificada

- **Requisitos sem critério:** os RFs do PRD encontram critérios gerais em AC1–AC12, mas a relação não é formalizada requisito a requisito; RNF02, RNF04, RNF06 e várias regras de erro/concorrência não têm teste de aceitação dedicado.
- **Regras sem critério específico:** RN03 (pause), RN04 (step), RN05 (Page Fault), RN07 (erros de transição) são parcialmente cobertas por AC4–AC7/AC11, mas falta testar estados, códigos e corpo de resposta detalhadamente.
- **Objetivo sem validação:** efetividade da aprendizagem.
- **Requisito sem relação clara:** nenhum RF central parece totalmente desconectado; campos detalhados do frame/CRC precisam de justificativa (A-09).
- **Duplicações:** exclusividade está expressa em ERS RNF01 e RN02 e reaparece como RNF01/RN02 no PRD; são consistentes, mas há sobreposição entre qualidade técnica e regra de negócio. Poderiam ser referenciadas em vez de repetidas.

## I. Correções recomendadas

As redações abaixo são sugestões, não novas aprovações de produto.

### 1. Alinhar transporte de eventos

**Definição atual:** ERS permite WebSocket/SSE; PRD escolhe SSE; catálogo descreve WebSocket.

**Redação sugerida:** “O fluxo de eventos do ArchPath utiliza SSE (`text/event-stream`) com payload JSON. Os comandos do cliente são enviados por REST. O catálogo define o schema dos dados e não especifica WebSocket.”

**Impacto:** atualizar ERS RF02, catálogo, diagrama de componentes e contrato API.

### 2. Normalizar FSM e step

**Definição atual:** `AGUARDANDO_STEP` existe no PRD/schema, enquanto diagramas e texto alternam entre estado de pausa e avanço.

**Redação sugerida:** adotar a unidade de avanço e as transições da tabela na seção F, após confirmação do Product Owner; documentar estado observado no início/fim de cada evento.

**Impacto:** ERS RF03, PRD §§7/9/10, OpenAPI, catálogo e diagrama de controle.

### 3. Resolver Page Fault e estado terminal

**Definição atual:** PRD define fatal; ERS é neutro; exemplo declara swapping/PAUSADO.

**Redação sugerida, se fatal aprovado:** “O cenário `page_fault` encerra a simulação antes da alocação. O evento de erro registra `FINALIZADO`; a sessão libera o lock e não há eventos DMA/rede.”

**Impacto:** ERS RF06, schema e exemplo de Page Fault, estado/status, AC7, AC12.

### 4. Definir ciclo de vida do recurso da sessão

**Definição atual:** o PRD descreve `FINALIZADO` e `OCIOSO`, mas não diz quando recursos são liberados nem o que status retorna após término.

**Proposta pendente:** declarar se `FINALIZADO` é visível em `GET status` até novo início ou se a liberação imediata retorna `404/OCIOSO`. Documentar lock, buffers e registradores em término normal, Page Fault e falha interna.

**Impacto:** RN02/RN07, endpoint de status/início, schema e critérios de aceitação.

### 5. Formalizar API e eventos

Definir em especificação única:

- endpoint SSE e tipo de conteúdo;
- schema de erro e respostas de todos os endpoints;
- resposta de `step` (imediata ou após a etapa);
- comportamento quando cliente desconecta;
- sincronização via status após reconexão e existência/não existência de replay;
- ordenação e relação entre timestamp, estado da FSM e transformação.

Os detalhes que impliquem funcionalidade nova (replay, cancelamento, autenticação) dependem de decisão e não devem ser presumidos.

### 6. Formalizar entrada, valores didáticos e não funcionais

- Especificar entradas suportadas para `tecla_entrada` e valor default normativo de `cenario_memoria`.
- Rotular dados do catálogo como exemplos ou valores fixos normativos.
- Decidir se qualidade de aprendizagem e metas de desempenho são requisitos desta versão; sem decisão, não inventar indicadores ou limites.
- Esclarecer se single-user significa processo único ou serviço distribuído com coordenação entre instâncias.

## J. Plano de ação

### Bloqueadoras antes de aprovar a documentação para desenvolvimento integrado

1. **P1 — A-01:** consolidar SSE/WebSocket em todos os documentos e formalizar a rota de eventos.
2. **P1 — A-02:** aprovar a semântica e unidade de avanço da FSM; atualizar os diagramas.
3. **P1 — A-03:** validar Page Fault fatal versus recuperável e corrigir a descrição/evento correspondente.
4. **P1 — A-04:** aprovar enumeração de estados e ciclo de vida/status terminal.
5. **P1 — A-05:** fixar a regra de não sobrescrever sessão ativa e delimitar alcance do lock.

### Alta prioridade antes de implementar as funcionalidades afetadas

1. **P2 — A-06/A-07:** consolidar schema de evento, endpoint, reconexão e sincronização por status.
2. **P2 — A-08:** determinar se serão definidas metas verificáveis de desempenho e/ou aprendizagem.
3. **P2 — A-09:** separar exemplos de rede normativos e ilustrativos.
4. Documentar validação de `tecla_entrada`, default de `cenario_memoria`, erros dos comandos e finalização após falha.
5. Criar testes de transições, concorrência, desconexão SSE e cenários Page Fault normal/fatal, conforme decisões aprovadas.

### Melhorias posteriores

1. Formalizar uma matriz de rastreabilidade mantida junto ao ERS/PRD e testes.
2. Revisar duplicação entre requisitos de exclusividade e regras de negócio.
3. Versionar o contrato de eventos/API quando houver mudanças de compatibilidade.
4. Se a proposta pedagógica exigir avaliação de eficácia, planejar validação com usuários sem confundir essa pesquisa com testes funcionais.

## K. Veredito da auditoria inicial

1. **A documentação expressa claramente o propósito?** Sim. O simulador mostra a jornada do dado para fins pedagógicos.
2. **O escopo está definido e consistente?** Em grande parte. O escopo nominal está claro, mas a exceção de memória, término e contrato de eventos ainda divergem entre artefatos.
3. **Os requisitos são completos, coerentes e verificáveis?** Parcialmente. O fluxo nominal é verificável; estados, entradas, falhas e transporte precisam de consolidação.
4. **Existem contradições?** Sim: principalmente SSE/WebSocket, pausa/step, Page Fault fatal/swapping e estados terminais/inativos.
5. **Existem decisões importantes não tomadas?** Sim: retenção do estado final, semântica precisa de step/pause, comportamento de falha interna, reconexão/event replay, domínio de entrada e topologia suportada para single-user.
6. **Os documentos são suficientes para orientar o desenvolvimento?** Suficientes para prototipar a jornada pedagógica se o PRD for tomado como referência, mas insuficientes para integração confiável sem resolver P1.
7. **O que resolver antes de iniciar a implementação?** Para o núcleo, aprovar estados/unidade de step e Page Fault. Para integração ponta a ponta, alinhar transporte/schema e contrato de sessão. Para deploy concorrente, confirmar topologia e alcance do lock.
8. **Classificação:** **Aprovada com ressalvas.** A documentação pode orientar o desenvolvimento após as decisões P1 serem atribuídas e resolvidas antes de implementar as áreas afetadas. Não se recomenda considerar os contratos técnicos prontos para integração enquanto as divergências persistirem.

**O que está bem especificado:** finalidade, sequência nominal, papéis dos subsistemas, caráter pedagógico, exclusividade de sessão e separação geral entre motor e cliente.

**O que precisa de revisão:** contrato de eventos/transporte, tabela FSM, Page Fault, término/status/limpeza, validação de entrada e limites de implantação single-user.

## L. Reavaliação após harmonização

**Data:** 16 de outubro de 2026. Esta seção atualiza o parecer da auditoria inicial acima, que registrava as pendências antes da harmonização. As alterações documentais adotaram as decisões confirmadas pelo responsável do produto.

### Decisões consolidadas e alterações

| Achado inicial | Decisão aplicada | Documentos harmonizados |
|---|---|---|
| A-01 — SSE/WebSocket | SSE é o único transporte; `GET /api/simulacao/eventos`, `text/event-stream`, IDs `<sessao_id>:<sequencia>` e replay em memória via `Last-Event-ID`. Sem replay persistente após reinício. | ERS, PRD, OpenAPI, catálogo SSE, diagrama de componentes e diagramas de atividades. O catálogo antigo foi substituído por [Catálogo de eventos SSE](./documentos-extras/2-Catálogo%20de%20Eventos%20SSE%20e%20Schemas%20JSON.txt). |
| A-02 — pausa/step/FSM | `step` executa uma transição completa de componente; `AGUARDANDO_STEP` é transitório; a resposta ocorre após a transição e evento. `pause` deixa a transição atual terminar e suspende antes da próxima. | ERS, PRD, OpenAPI, arquitetura de erros e diagrama de controle. |
| A-03 — Page Fault | Cenário opcional e fatal; sem swapping/retomada, sem alocação nem eventos DMA/rede subsequentes. Emite evento `ERRO` com `FINALIZADO`. | ERS, PRD, catálogo, arquitetura de erros, diagrama de memória e jornada. |
| A-04 — estados e ciclo de vida | `FINALIZADO` é comunicado por evento terminal; lock/recursos são liberados imediatamente e o serviço volta a OCIOSO. `GET status` então retorna 404/OCIOSO. Histórico SSE permanece até novo início aceito. | ERS, PRD, OpenAPI, catálogo, arquitetura de erros e diagramas. |
| A-05 — inicialização/concorrência | Uma instância/processo, lock atômico e comandos serializados. Início ativo retorna 409 sem modificar contexto. | ERS, PRD, OpenAPI e arquitetura de erros/concorrência. |
| A-06 — contrato de eventos | Schema unificado com `sessao_id`, timestamp, estado, módulo, componente, tipo, ação e snapshot; ordenação usa sequência, não timestamp. | ERS, PRD, OpenAPI e catálogo SSE. |
| A-07 — entrada | A API aceita uma letra maiúscula `A–Z`, algarismo `0–9` ou espaço; restantes retornam 400; cenário omitido equivale a `normal`. Scancodes didáticos set 1 estão tabelados no apêndice do ERS. | ERS, PRD, OpenAPI e diagrama de Módulo 1. |
| A-08 — métricas e acesso | MVP sem metas quantitativas de desempenho ou eficácia pedagógica. Execução em localhost/rede privada confiável, sem autenticação; mesma origem preferida e CORS restrito se necessário. | ERS, PRD, OpenAPI e arquitetura de erros/acesso. |
| A-09 — rede ilustrativa | UDP é o protocolo de transporte fixo. Valores de endereços, frame e CRC são ilustrativos, sem promessa de transmissão externa ou cálculo bit-exato. | ERS, PRD, catálogo SSE e diagrama de Módulo 4. |

### Reanálise final

- **Propósito e escopo:** claros e proporcionais; o sistema é explicitamente uma simulação pedagógica, não uma emulação física ou rede externa.
- **Requisitos funcionais:** o fluxo nominal, as entradas aceitas, os cenários de memória e o encerramento estão definidos e associados a critérios observáveis.
- **FSM e concorrência:** estados, guardas, unidade de passo, pausa, terminalidade, lock e topologia de instância única estão documentados de forma compatível.
- **Contratos de integração:** as rotas REST, esquemas de entrada/saída, códigos de erro, schema dos eventos, SSE, ordenação, replay e comportamento sem histórico estão documentados em conjunto.
- **Falhas:** Page Fault e erro interno irrecuperável terminam explicitamente; as rejeições de estado não alteram a sessão; desconexão SSE não cancela o motor.
- **Rastreabilidade/testabilidade:** ERS e PRD incluem critérios gerais; o relatório mantém a matriz relacionando objetivos, requisitos, regras e critérios. O comportamento agora admite testes funcionais e negativos sem pressupor desempenho ou aprendizagem mensuráveis.

### Pendências residuais

1. Os arquivos continuam sendo especificações documentais; a implementação deverá cumprir e testar os contratos, não há evidência de código ou testes nesta auditoria.
2. O mapa de scancodes é uma abstração set 1 declarada explicitamente e não representa HID USB real.
3. O schema permite `estado_do_dado` variar por componente; consumidores devem tratar propriedades internas conforme `tipo_evento`/`componente_atual`. Não se exige schema rígido para cada payload por componente nesta versão.
4. O deployment público, autenticação, multi-instância, persistência após reinício e metas quantitativas permanecem fora do escopo aprovado, não como decisões pendentes desta versão.

### Veredito atualizado

**Aprovada para desenvolvimento**, quanto à suficiência documental da primeira versão single-processo/privada. ERS, PRD, diagramas, OpenAPI, catálogo SSE e arquitetura de erros agora descrevem o mesmo comportamento essencial para implementar e integrar o fluxo. A aprovação não comprova implementação, segurança para exposição pública, conformidade de runtime ou eficácia educacional; essas propriedades estão fora do escopo declarado.
