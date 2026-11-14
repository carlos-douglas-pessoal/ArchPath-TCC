# Análise do problema de sincronização ao pausar

## Diagnóstico

A causa mais provável **não é um atraso de 1000 ms no envio do comando ao
backend**. O que encontrei é um descompasso entre a cadência do motor e a
apresentação dos eventos:

- O motor do backend espera **250 ms** entre transições, em
  [`simulation_manager.py`](../backend/app/application/simulation_manager.py).
- A interface espera **1000 ms** antes de apresentar cada evento e os coloca em
  uma fila, em [`App.tsx`](../frontend/src/App.tsx).
- Ao receber “Pausar”, o backend marca a sessão para pausar, mas conclui a
  transição que já está em andamento antes de responder. Isso é intencional e
  corresponde à semântica descrita no [PRD](./prd.md).
- Enquanto isso, a fila visual continua apresentando os eventos que já
  recebeu. O snapshot é atualizado a partir desses mesmos eventos; portanto,
  ele também continua mudando mesmo que o backend já tenha pausado.

Com esses ritmos, o motor pode produzir quatro eventos no tempo que a
interface leva para apresentar um. Isso explica a impressão de que a pausa
demorou a chegar ao backend: a animação e o snapshot visíveis podem estar
reproduzindo eventos antigos.

## Análise das hipóteses

### 1. Ocultar o conteúdo enquanto pausa

Mostrar um estado intermediário **“Pausando…”** é útil, mas esconder todo o
texto com a cor do fundo não resolve a causa. Além de esconder informações
válidas, prejudica a acessibilidade e pode ocultar erros. Também não recomendo
iniciar novamente a simulação como parte da pausa.

### 2. Fazer o frontend solicitar cada avanço

É uma solução possível se o produto quiser que a velocidade visual determine o
ritmo da simulação. Porém, mudaria o contrato atual: o backend deixaria de
executar independentemente da interface, e avançar automaticamente passaria a
depender do navegador. Isso conflita com os requisitos atuais de motor
independente e atualizações via SSE documentados no [PRD](./prd.md). Exigiria
rever API, FSM, reconexão e testes.

## Solução recomendada

Preservar a arquitetura atual e corrigir a sincronização na fronteira entre
backend e apresentação.

1. Ao clicar em **Pausar**, a interface mostra imediatamente **“Pausando…”**,
   cancela o timer visual em andamento e segura a fila. Assim, o snapshot não
   continua mudando enquanto o backend conclui a transição.
2. O backend conclui e publica a transição em andamento, suspende antes da
   próxima e responde com `sessao_id`, `sequencia_evento` e o payload `evento`
   da última transição publicada.
3. O frontend usa essa confirmação como cursor: registra em ordem os eventos
   já recebidos até a sequência confirmada, atualiza o snapshot para o evento
   confirmado como `PAUSADO` e descarta da fila visual qualquer evento antigo
   até esse limite.
4. Eventos SSE atrasados cuja sequência seja igual ou inferior ao cursor podem
   completar o histórico visual, mas não alteram o snapshot nem retomam a
   animação.
5. `step` retorna a mesma confirmação de sessão/sequência/evento; o cliente
   atualiza o snapshot diretamente para essa transição e permanece pausado.
   `resume` libera a fila para os eventos posteriores ao cursor.

Assim, a interface não perde eventos nem continua exibindo uma fila obsoleta
após a confirmação.

### Alinhar as cadências

Como medida complementar, alinhar o intervalo do motor à cadência pretendida
para apresentação evitaria que a fila crescesse continuamente. Isso tornaria a
jornada completa mais lenta; portanto, é uma decisão de produto, não apenas uma
correção de transporte. A implementação recomendada não altera a cadência atual
do backend: a confirmação por sequência trata o descompasso sem desacelerar a
simulação lógica.

## Critérios de validação

A implementação deve confirmar que:

- após a resposta de pausa, o último evento apresentado corresponde ao limite
  confirmado pelo backend;
- o snapshot permanece estável enquanto pausado;
- **Avançar uma etapa** apresenta exatamente a transição solicitada;
- **Retomar** continua sem reproduzir eventos antigos fora de ordem.

O teste deve usar a velocidade fixa de **1000 ms**.