export const supportedCharacter = /^[A-Z0-9 ]$/;

export type SimulationState =
  | "OCIOSO"
  | "RODANDO"
  | "PAUSADO"
  | "AGUARDANDO_STEP"
  | "FINALIZADO";

export type SimulationEvent = {
  timestamp: string;
  sessao_id: string;
  status_fsm: "RODANDO" | "PAUSADO" | "FINALIZADO";
  modulo_atual: string;
  componente_atual: string;
  tipo_evento: "TRANSICAO" | "ERRO" | "FINALIZACAO";
  acao_executada: string;
  estado_do_dado: Record<string, unknown>;
};

export type SequencedEvent = {
  event: SimulationEvent;
  sequence: number;
};

export type ActiveStatus = {
  sessao_id: string;
  estado_fsm: "RODANDO" | "PAUSADO" | "AGUARDANDO_STEP";
  modulo_atual: string;
  componente_atual: string;
  timestamp_ultima_acao: string;
};

export type IdleStatus = {
  estado_fsm: "OCIOSO";
  mensagem: string;
};

export type ControlResponse = {
  mensagem: string;
  estado_fsm: "RODANDO" | "PAUSADO" | "FINALIZADO";
  resultado?: "sucesso" | "erro";
  sessao_id?: string;
  sequencia_evento?: number;
  evento?: SimulationEvent;
};

export type StartResponse = {
  mensagem: string;
  estado_fsm: "RODANDO";
  sessao_id: string;
  timestamp_inicio: string;
};

export type StatusResponse = ActiveStatus | IdleStatus;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  parse: (payload: unknown) => T,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? error.message : "Falha de conexão com a API.",
      0,
    );
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      isRecord(payload) && typeof payload.erro === "string"
        ? payload.erro
        : response.status === 409
          ? "Já existe uma simulação ativa."
          : `A solicitação falhou (HTTP ${response.status}).`;
    throw new ApiError(message, response.status);
  }
  return parse(payload);
}

export async function fetchStatus(): Promise<StatusResponse> {
  try {
    return await request("/api/simulacao/status", parseActiveStatus);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return {
        estado_fsm: "OCIOSO",
        mensagem: "Não há simulação ativa.",
      };
    }
    throw error;
  }
}

export function startSimulation(
  character: string,
  scenario: "normal" | "page_fault",
): Promise<StartResponse> {
  return request(
    "/api/simulacao/iniciar",
    parseStartResponse,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tecla_entrada: character,
        cenario_memoria: scenario,
      }),
    },
  );
}

export function sendCommand(
  command: "pause" | "resume" | "step",
): Promise<ControlResponse> {
  return request(`/api/simulacao/${command}`, parseControlResponse, { method: "POST" });
}

export function parseSequencedEvent(message: MessageEvent<string>): SequencedEvent | null {
  const separator = message.lastEventId.lastIndexOf(":");
  if (separator < 1) return null;

  const sequence = Number(message.lastEventId.slice(separator + 1));
  if (!Number.isSafeInteger(sequence) || sequence < 1) return null;

  let payload: unknown;
  try {
    payload = JSON.parse(message.data);
  } catch {
    return null;
  }
  if (!isSimulationEvent(payload)) return null;
  if (message.lastEventId.slice(0, separator) !== payload.sessao_id) return null;

  return { event: payload, sequence };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function invalidApiResponse(): never {
  throw new Error("A API retornou uma resposta fora do contrato esperado.");
}

function isControlState(value: unknown): value is ControlResponse["estado_fsm"] {
  return value === "RODANDO" || value === "PAUSADO" || value === "FINALIZADO";
}

function isActiveStatusState(value: unknown): value is ActiveStatus["estado_fsm"] {
  return value === "RODANDO" || value === "PAUSADO" || value === "AGUARDANDO_STEP";
}

function parseStartResponse(payload: unknown): StartResponse {
  if (
    !isRecord(payload) ||
    payload.estado_fsm !== "RODANDO" ||
    typeof payload.mensagem !== "string" ||
    typeof payload.sessao_id !== "string" ||
    typeof payload.timestamp_inicio !== "string" ||
    !Number.isFinite(Date.parse(payload.timestamp_inicio))
  ) {
    return invalidApiResponse();
  }
  return {
    mensagem: payload.mensagem,
    estado_fsm: payload.estado_fsm,
    sessao_id: payload.sessao_id,
    timestamp_inicio: payload.timestamp_inicio,
  };
}

function parseControlResponse(payload: unknown): ControlResponse {
  const cursorProvided =
    isRecord(payload) &&
    (payload.sessao_id !== undefined ||
      payload.sequencia_evento !== undefined ||
      payload.evento !== undefined);
  const eventCursor = parseControlEventCursor(payload);
  if (
    !isRecord(payload) ||
    typeof payload.mensagem !== "string" ||
    !isControlState(payload.estado_fsm) ||
    (payload.resultado !== undefined &&
      payload.resultado !== "sucesso" &&
      payload.resultado !== "erro") ||
    (cursorProvided && eventCursor === null)
  ) {
    return invalidApiResponse();
  }
  return {
    mensagem: payload.mensagem,
    estado_fsm: payload.estado_fsm,
    ...(payload.resultado === undefined ? {} : { resultado: payload.resultado }),
    ...(eventCursor ?? {}),
  };
}

function parseControlEventCursor(
  payload: unknown,
): Pick<ControlResponse, "sessao_id" | "sequencia_evento" | "evento"> | null {
  if (
    !isRecord(payload) ||
    typeof payload.sessao_id !== "string" ||
    typeof payload.sequencia_evento !== "number" ||
    !Number.isSafeInteger(payload.sequencia_evento) ||
    payload.sequencia_evento < 1 ||
    !isSimulationEvent(payload.evento) ||
    payload.evento.sessao_id !== payload.sessao_id ||
    payload.evento.status_fsm !== payload.estado_fsm
  ) {
    return null;
  }
  return {
    sessao_id: payload.sessao_id,
    sequencia_evento: payload.sequencia_evento,
    evento: payload.evento,
  };
}

function parseActiveStatus(payload: unknown): ActiveStatus {
  if (
    !isRecord(payload) ||
    typeof payload.sessao_id !== "string" ||
    !isActiveStatusState(payload.estado_fsm) ||
    typeof payload.modulo_atual !== "string" ||
    typeof payload.componente_atual !== "string" ||
    typeof payload.timestamp_ultima_acao !== "string" ||
    !Number.isFinite(Date.parse(payload.timestamp_ultima_acao))
  ) {
    return invalidApiResponse();
  }
  return {
    sessao_id: payload.sessao_id,
    estado_fsm: payload.estado_fsm,
    modulo_atual: payload.modulo_atual,
    componente_atual: payload.componente_atual,
    timestamp_ultima_acao: payload.timestamp_ultima_acao,
  };
}

function isSimulationEvent(value: unknown): value is SimulationEvent {
  return (
    isRecord(value) &&
    typeof value.timestamp === "string" &&
    typeof value.sessao_id === "string" &&
    ["RODANDO", "PAUSADO", "FINALIZADO"].includes(String(value.status_fsm)) &&
    typeof value.modulo_atual === "string" &&
    typeof value.componente_atual === "string" &&
    ["TRANSICAO", "ERRO", "FINALIZACAO"].includes(String(value.tipo_evento)) &&
    typeof value.acao_executada === "string" &&
    isRecord(value.estado_do_dado)
  );
}

export const journeyPhases = [
  {
    name: "Nascimento do dado",
    components: ["MatrizContatos", "MicrocontroladorTeclado", "CaboConexao"],
  },
  {
    name: "I/O",
    components: [
      "PortaFisica",
      "ControladorInterface",
      "Chipset",
      "APIC",
      "BarramentoSistema",
    ],
  },
  { name: "CPU", components: ["UnidadeControle"] },
  { name: "Sistema Operacional", components: ["DriverTecladoOS"] },
  {
    name: "Memória",
    components: ["GerenciadorMemoria", "BufferTemporario"],
  },
  { name: "DMA", components: ["ControladorDMA"] },
  {
    name: "Rede",
    components: [
      "L7_Aplicacao",
      "L6_Apresentacao",
      "L5_Sessao",
      "L4_Transporte",
      "L3_Rede",
      "ControladorMAC",
      "SRAM",
    ],
  },
  { name: "Saída Física", components: ["ControladorPHY"] },
] as const;

export function isActiveState(state: SimulationState): boolean {
  return state === "RODANDO" || state === "PAUSADO" || state === "AGUARDANDO_STEP";
}
