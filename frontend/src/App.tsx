import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  fetchStatus,
  isActiveState,
  journeyPhases,
  parseSequencedEvent,
  sendCommand,
  startSimulation,
  supportedCharacter,
  type SequencedEvent,
  type SimulationEvent,
  type SimulationState,
  type StatusResponse,
} from "./simulation";
import "./styles.css";

type PresentedEvent = SequencedEvent & { id: string };
type Scenario = "normal" | "page_fault";
type TerminalResult = "sucesso" | "erro";

const VISUAL_EVENT_INTERVAL_MS = 0.25;

function statusFromResponse(status: StatusResponse): SimulationState {
  return status.estado_fsm;
}

function App() {
  const [character, setCharacter] = useState("");
  const [scenario, setScenario] = useState<Scenario>("normal");
  const [state, setState] = useState<SimulationState>("OCIOSO");
  const [component, setComponent] = useState<string | null>(null);
  const [phase, setPhase] = useState<string | null>(null);
  const [currentEvent, setCurrentEvent] = useState<SimulationEvent | null>(null);
  const [terminalResult, setTerminalResult] = useState<TerminalResult | null>(null);
  const [eventLog, setEventLog] = useState<PresentedEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [pausePending, setPausePending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connection, setConnection] = useState("Conectando aos eventos…");
  const [statusLoading, setStatusLoading] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const sourceRef = useRef<EventSource | null>(null);
  const pendingBySessionRef = useRef(new Map<string, Map<number, PresentedEvent>>());
  const receivedEventsRef = useRef(new Map<string, Map<number, PresentedEvent>>());
  const nextSequenceBySessionRef = useRef(new Map<string, number>());
  const seenIdsRef = useRef(new Set<string>());
  const ignoredSessionIdRef = useRef<string | null>(null);
  const currentStreamSessionRef = useRef<string | null>(null);
  const visualQueueRef = useRef<PresentedEvent[]>([]);
  const processingRef = useRef(false);
  const visualTimerRef = useRef<number | null>(null);
  const processQueueRef = useRef<() => void>(() => undefined);
  const presentationHeldRef = useRef(false);
  const pausedThroughRef = useRef<{ sessionId: string; sequence: number } | null>(null);
  const syncInProgressRef = useRef(false);
  const statusGenerationRef = useRef(0);
  const presentedEventVersionRef = useRef(0);

  const synchronizeStatus = useCallback(async (preserveExistingError = false) => {
    if (syncInProgressRef.current) return;
    syncInProgressRef.current = true;
    const generation = ++statusGenerationRef.current;
    try {
      const status = await fetchStatus();
      if (generation !== statusGenerationRef.current) return;
      setState(statusFromResponse(status));
      if (status.estado_fsm === "OCIOSO") {
        setSessionId(null);
        setComponent(null);
        setPhase(null);
        presentedEventVersionRef.current = 0;
      } else {
        setSessionId(status.sessao_id);
        setComponent(status.componente_atual);
        setPhase(status.modulo_atual);
      }
      if (!preserveExistingError) setError(null);
    } catch {
      if (generation === statusGenerationRef.current) {
        setError(
          (current) =>
            current ??
            "Não foi possível consultar o estado da simulação. Verifique a conexão e tente novamente.",
        );
      }
    } finally {
      if (generation === statusGenerationRef.current) {
        syncInProgressRef.current = false;
        setStatusLoading(false);
      }
    }
  }, []);

  const clearSessionPresentation = useCallback(() => {
    if (visualTimerRef.current !== null) {
      window.clearTimeout(visualTimerRef.current);
      visualTimerRef.current = null;
    }
    processingRef.current = false;
    pendingBySessionRef.current.clear();
    receivedEventsRef.current.clear();
    nextSequenceBySessionRef.current.clear();
    seenIdsRef.current.clear();
    visualQueueRef.current = [];
    currentStreamSessionRef.current = null;
    presentationHeldRef.current = false;
    pausedThroughRef.current = null;
    setPausePending(false);
    setEventLog([]);
    setCurrentEvent(null);
    setTerminalResult(null);
    setComponent(null);
    setPhase(null);
  }, []);

  processQueueRef.current = () => {
    if (processingRef.current || presentationHeldRef.current) return;
    const next = visualQueueRef.current.shift();
    if (!next) return;

    processingRef.current = true;
    visualTimerRef.current = window.setTimeout(() => {
      setCurrentEvent(next.event);
      setComponent(next.event.componente_atual);
      setPhase(next.event.modulo_atual);
      if (next.event.status_fsm === "FINALIZADO") {
        setState("FINALIZADO");
      }
      setSessionId(next.event.sessao_id);
      presentedEventVersionRef.current += 1;
      if (next.event.status_fsm === "FINALIZADO") {
        setTerminalResult(next.event.tipo_evento === "ERRO" ? "erro" : "sucesso");
      }
      setEventLog((current) => [...current, next].slice(-200));
      processingRef.current = false;
      visualTimerRef.current = null;
      processQueueRef.current();
    }, VISUAL_EVENT_INTERVAL_MS);
  };

  const receiveEvent = useCallback((message: MessageEvent<string>) => {
    const parsed = parseSequencedEvent(message);
    if (!parsed) {
      setError("Um evento recebido não corresponde ao formato esperado.");
      return;
    }

    const id = `${parsed.event.sessao_id}:${parsed.sequence}`;
    if (ignoredSessionIdRef.current === parsed.event.sessao_id) return;
    if (seenIdsRef.current.has(id)) return;

    if (
      currentStreamSessionRef.current !== null &&
      currentStreamSessionRef.current !== parsed.event.sessao_id &&
      parsed.sequence === 1
    ) {
      clearSessionPresentation();
    }
    currentStreamSessionRef.current ??= parsed.event.sessao_id;
    seenIdsRef.current.add(id);

    const received = receivedEventsRef.current.get(parsed.event.sessao_id) ?? new Map();
    const presented = { ...parsed, id };
    received.set(parsed.sequence, presented);
    receivedEventsRef.current.set(parsed.event.sessao_id, received);

    const pausedThrough = pausedThroughRef.current;
    if (
      pausedThrough?.sessionId === parsed.event.sessao_id &&
      parsed.sequence <= pausedThrough.sequence
    ) {
      setEventLog(
        [...received.values()]
          .filter((item) => item.sequence <= pausedThrough.sequence)
          .sort((left, right) => left.sequence - right.sequence)
          .slice(-200),
      );
      return;
    }

    const pending = pendingBySessionRef.current.get(parsed.event.sessao_id) ?? new Map();
    pending.set(parsed.sequence, presented);
    pendingBySessionRef.current.set(parsed.event.sessao_id, pending);

    let expected = nextSequenceBySessionRef.current.get(parsed.event.sessao_id) ?? 1;
    while (pending.has(expected)) {
      const next = pending.get(expected);
      if (!next) break;
      pending.delete(expected);
      visualQueueRef.current.push(next);
      expected += 1;
    }
    nextSequenceBySessionRef.current.set(parsed.event.sessao_id, expected);
    processQueueRef.current();
  }, [clearSessionPresentation]);

  useEffect(() => {
    void synchronizeStatus();
    try {
      const source = new EventSource("/api/simulacao/eventos");
      sourceRef.current = source;
      source.onopen = () => setConnection("Conectado aos eventos");
      source.onmessage = receiveEvent;
      source.onerror = () => {
        setConnection("Reconectando aos eventos…");
        void synchronizeStatus();
      };
    } catch {
      setConnection("Não foi possível conectar aos eventos");
      setError("Não foi possível abrir a conexão de eventos. A simulação continua independente dela.");
    }

    return () => {
      sourceRef.current?.close();
      sourceRef.current = null;
      if (visualTimerRef.current !== null) {
        window.clearTimeout(visualTimerRef.current);
      }
    };
  }, [receiveEvent, synchronizeStatus]);

  const submitStart = async (formEvent: React.FormEvent<HTMLFormElement>) => {
    formEvent.preventDefault();
    if (!supportedCharacter.test(character) || busy || isActiveState(state)) return;

    setBusy(true);
    setError(null);
    statusGenerationRef.current += 1;
    syncInProgressRef.current = false;
    clearSessionPresentation();
    const eventVersion = presentedEventVersionRef.current;
    try {
      const result = await startSimulation(character, scenario);
      ignoredSessionIdRef.current = null;
      setSessionId(result.sessao_id);
      if (
        currentStreamSessionRef.current !== result.sessao_id ||
        presentedEventVersionRef.current === eventVersion
      ) {
        setState(result.estado_fsm);
        if (presentedEventVersionRef.current === eventVersion) {
          setComponent(journeyPhases[0].components[0]);
          setPhase(journeyPhases[0].name);
        }
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível iniciar a simulação.",
      );
      if (requestError instanceof Error && "status" in requestError && requestError.status === 409) {
        void synchronizeStatus(true);
      }
    } finally {
      setBusy(false);
      setStatusLoading(false);
    }
  };

  const presentConfirmedEvent = (result: Awaited<ReturnType<typeof sendCommand>>) => {
    const { sessao_id: confirmedSessionId, sequencia_evento: sequence, evento } = result;
    if (!confirmedSessionId || !sequence || !evento) {
      throw new Error("A API não confirmou o evento correspondente ao controle.");
    }

    if (visualTimerRef.current !== null) {
      window.clearTimeout(visualTimerRef.current);
      visualTimerRef.current = null;
    }
    processingRef.current = false;
    visualQueueRef.current = visualQueueRef.current.filter(
      (item) =>
        item.event.sessao_id !== confirmedSessionId ||
        item.sequence > sequence,
    );

    const id = `${confirmedSessionId}:${sequence}`;
    const confirmed: PresentedEvent = {
      event: evento,
      sequence,
      id,
    };
    const received = receivedEventsRef.current.get(confirmedSessionId) ?? new Map();
    received.set(sequence, confirmed);
    receivedEventsRef.current.set(confirmedSessionId, received);
    const pending = pendingBySessionRef.current.get(confirmedSessionId);
    if (pending) {
      for (const pendingSequence of pending.keys()) {
        if (pendingSequence <= sequence) pending.delete(pendingSequence);
      }
    }
    nextSequenceBySessionRef.current.set(
      confirmedSessionId,
      Math.max(nextSequenceBySessionRef.current.get(confirmedSessionId) ?? 1, sequence + 1),
    );
    setEventLog(
      [...received.values()]
        .filter((item) => item.sequence <= sequence)
        .sort((left, right) => left.sequence - right.sequence)
        .slice(-200),
    );

    presentationHeldRef.current = result.estado_fsm === "PAUSADO";
    pausedThroughRef.current =
      result.estado_fsm === "PAUSADO"
        ? { sessionId: confirmedSessionId, sequence }
        : null;
    setCurrentEvent(evento);
    setComponent(evento.componente_atual);
    setPhase(evento.modulo_atual);
    setSessionId(confirmedSessionId);
    setState(result.estado_fsm);
    setTerminalResult(
      result.estado_fsm === "FINALIZADO"
        ? result.resultado ?? (evento.tipo_evento === "ERRO" ? "erro" : "sucesso")
        : null,
    );
    presentedEventVersionRef.current += 1;
  };

  const runCommand = async (command: "pause" | "resume" | "step") => {
    if (busy) return;
    setBusy(true);
    setError(null);
    statusGenerationRef.current += 1;
    syncInProgressRef.current = false;
    if (command === "pause") {
      setPausePending(true);
      presentationHeldRef.current = true;
      if (visualTimerRef.current !== null) {
        window.clearTimeout(visualTimerRef.current);
        visualTimerRef.current = null;
      }
      processingRef.current = false;
    } else if (command === "step") {
      setState("AGUARDANDO_STEP");
    }
    try {
      const result = await sendCommand(command);
      setError(null);
      if (command === "pause") setPausePending(false);
      if (command === "pause" || command === "step") {
        presentConfirmedEvent(result);
      } else {
        setState(result.estado_fsm);
        presentationHeldRef.current = false;
        pausedThroughRef.current = null;
        processQueueRef.current();
      }
      if (!isActiveState(result.estado_fsm)) setSessionId(null);
    } catch (requestError) {
      setPausePending(false);
      if (command === "pause") {
        presentationHeldRef.current = false;
        processQueueRef.current();
      }
      if (
        requestError instanceof ApiError &&
        requestError.status === 400 &&
        requestError.message === "Não há simulação ativa."
      ) {
        ignoredSessionIdRef.current = sessionId;
        clearSessionPresentation();
        setError("A simulação já foi concluída.");
        await synchronizeStatus(true);
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível executar o comando.",
      );
      void synchronizeStatus(true);
    } finally {
      setBusy(false);
      setStatusLoading(false);
    }
  };

  const validCharacter = supportedCharacter.test(character);
  const isRunning = state === "RODANDO";
  const isPaused = state === "PAUSADO";
  const activeComponent = component ?? "";
  const resultLabel = terminalResult;

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">SIMULADOR INTERATIVO DE ARQUITETURA</p>
          <h1>ArchPath</h1>
          <p className="hero-copy">
            Acompanhe a jornada de um dado, da tecla pressionada à saída física.
          </p>
        </div>
        <div className={`status-pill status-${state.toLowerCase()}`} aria-live="polite">
          <span className="status-dot" />
          {state}
        </div>
      </header>

      <section className="control-panel panel" aria-labelledby="controls-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">CONTROLE DA SIMULAÇÃO</p>
            <h2 id="controls-title">Configure e acompanhe</h2>
          </div>
          <p className="connection-state" aria-live="polite">{connection}</p>
        </div>
        <form className="start-form" onSubmit={submitStart}>
          <label className="field">
            <span>Caractere de entrada</span>
            <input
              autoComplete="off"
              aria-label="Caractere de entrada"
              aria-describedby="character-help"
              maxLength={1}
              onChange={(changeEvent) => setCharacter(changeEvent.target.value)}
              pattern="[A-Z0-9 ]"
              placeholder="A"
              type="text"
              value={character}
            />
            <small id="character-help">
              {character.length > 0 && !validCharacter
                ? "Use uma letra maiúscula, um algarismo ou espaço."
                : "Aceita letras maiúsculas, algarismos ou espaço."}
            </small>
          </label>
          <label className="field">
            <span>Cenário de memória</span>
            <select
              aria-label="Cenário de memória"
              onChange={(changeEvent) => setScenario(changeEvent.target.value as Scenario)}
              value={scenario}
            >
              <option value="normal">Normal — jornada completa</option>
              <option value="page_fault">Page Fault — falha fatal</option>
            </select>
          </label>
          <button className="button button-primary" disabled={!validCharacter || busy || isActiveState(state)}>
            {busy && state === "OCIOSO" ? "Iniciando…" : "Iniciar simulação"}
          </button>
        </form>

        <div className="command-row" aria-label="Controles da FSM">
          <button className="button button-secondary" disabled={!isRunning || busy} onClick={() => void runCommand("pause")}>
            Pausar
          </button>
          <button className="button button-secondary" disabled={!isPaused || busy} onClick={() => void runCommand("resume")}>
            Retomar
          </button>
          <button className="button button-secondary" disabled={!isPaused || busy} onClick={() => void runCommand("step")}>
            Avançar uma etapa
          </button>
          <label className="speed-control">
            <span>Velocidade visual (fixa)</span>
            <input
              aria-label="Velocidade visual"
              disabled
              max={VISUAL_EVENT_INTERVAL_MS}
              min={VISUAL_EVENT_INTERVAL_MS}
              type="range"
              value={VISUAL_EVENT_INTERVAL_MS}
            />
            <output>{VISUAL_EVENT_INTERVAL_MS} ms</output>
          </label>
        </div>
        {error && <p className="alert" role="alert">{error}</p>}
        {pausePending && (
          <p className="simulation-notice simulation-notice-pending" role="status">
            Pausando…
          </p>
        )}
        {state === "PAUSADO" && (
          <p className="simulation-notice simulation-notice-paused" role="status">
            Simulação pausada.
          </p>
        )}
        {statusLoading && <p className="muted status-loading">Consultando estado da simulação…</p>}
        {!statusLoading && state === "OCIOSO" && (
          <p className="muted idle-copy">Não há simulação ativa.</p>
        )}
        {sessionId && <p className="session-id">Sessão <code>{sessionId}</code></p>}
      </section>

      <div className="dashboard">
        <section className="journey-panel panel" aria-label="Jornada do dado">
          <div className="section-heading">
            <div>
              <p className="eyebrow">PERCURSO</p>
              <h2>Jornada do dado</h2>
            </div>
            <span className="muted">{eventLog.length} eventos apresentados</span>
          </div>
          <div className="phase-list">
            {journeyPhases.map((journeyPhase, index) => {
              const isCurrentPhase = phase === journeyPhase.name;
              const phaseReached = journeyPhases.findIndex((item) => item.name === phase);
              return (
                <section
                  className={`phase-card${isCurrentPhase ? " phase-current" : ""}${phaseReached > index ? " phase-complete" : ""}`}
                  key={journeyPhase.name}
                >
                  <div className="phase-title">
                    <span className="phase-index">{String(index + 1).padStart(2, "0")}</span>
                    <h3>{journeyPhase.name}</h3>
                    {isCurrentPhase && <span className="current-tag">ATUAL</span>}
                  </div>
                  <ul>
                    {journeyPhase.components.map((item) => (
                      <li
                        aria-current={activeComponent === item ? "step" : undefined}
                        className={activeComponent === item ? "component-active" : ""}
                        key={item}
                      >
                        <span className="component-marker" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>
        </section>

        <aside className="detail-column">
          <section className="panel detail-panel" aria-label="Estado do dado">
            <p className="eyebrow">SNAPSHOT ATUAL</p>
            <h2>Estado do dado</h2>
            {currentEvent ? (
              <>
                <p className="component-name">{currentEvent.componente_atual}</p>
                <p className="action-copy">{currentEvent.acao_executada}</p>
                {resultLabel && <p className={`result result-${resultLabel}`}>Resultado: {resultLabel}</p>}
                <pre>{JSON.stringify(currentEvent.estado_do_dado, null, 2)}</pre>
              </>
            ) : (
              <p className="muted">O snapshot aparecerá quando a jornada emitir o primeiro evento.</p>
            )}
          </section>

          <section className="panel events-panel" aria-label="Eventos recebidos">
            <p className="eyebrow">FLUXO SSE</p>
            <h2>Eventos recebidos</h2>
            {eventLog.length === 0 ? (
              <p className="muted">Aguardando eventos da simulação.</p>
            ) : (
              <ol className="event-list" aria-live="polite">
                {[...eventLog].reverse().map(({ event: item, sequence, id }) => (
                  <li key={id}>
                    <span className="event-sequence">#{sequence}</span>
                    <div>
                      <strong>{item.componente_atual}</strong>
                      <p>{item.acao_executada}</p>
                    </div>
                    <span className={`event-kind event-kind-${item.tipo_evento.toLowerCase()}`}>
                      {item.tipo_evento}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </aside>
      </div>
      <footer>
        <span>{connection}</span>
        <span>Velocidade ajusta apenas a apresentação no navegador; o motor mantém seu ritmo independente.</span>
      </footer>
    </main>
  );
}

export default App;
