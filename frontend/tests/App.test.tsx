import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";

class EventSourceMock {
  static instances: EventSourceMock[] = [];
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();

  constructor(readonly url: string) {
    EventSourceMock.instances.push(this);
  }

  emit(id: string, payload: Record<string, unknown>) {
    this.onmessage?.({
      data: JSON.stringify(payload),
      lastEventId: id,
    } as MessageEvent<string>);
  }
}

const statusIdle = () => new Response(
  JSON.stringify({ estado_fsm: "OCIOSO", mensagem: "Não há simulação ativa." }),
  { status: 404, headers: { "Content-Type": "application/json" } },
);

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const eventPayload = (
  component: string,
  overrides: Record<string, unknown> = {},
) => ({
  timestamp: "2026-10-17T10:00:00Z",
  sessao_id: "session-1",
  status_fsm: "RODANDO",
  modulo_atual: "I/O",
  componente_atual: component,
  tipo_evento: "TRANSICAO",
  acao_executada: `Ação em ${component}`,
  estado_do_dado: { exemplo: component },
  ...overrides,
});

const event = (
  component: string,
  sequence: number,
  overrides: Record<string, unknown> = {},
) => ({
  ...eventPayload(component, overrides),
  sequence,
});

beforeEach(() => {
  EventSourceMock.instances = [];
  vi.stubGlobal("EventSource", EventSourceMock);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(statusIdle()));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("ArchPath simulation interface", () => {
  it("renders the simulation controls and validates supported input", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "ArchPath" })).toBeInTheDocument();
    const input = screen.getByRole("textbox", { name: /caractere de entrada/i });
    expect(screen.getByRole("button", { name: /iniciar simulação/i })).toBeDisabled();

    fireEvent.change(input, { target: { value: "a" } });
    expect(screen.getByText(/use uma letra maiúscula, um algarismo ou espaço/i)).toBeVisible();
    expect(screen.getByRole("button", { name: /iniciar simulação/i })).toBeDisabled();

    fireEvent.change(input, { target: { value: "A" } });
    expect(screen.getByRole("button", { name: /iniciar simulação/i })).toBeEnabled();
    expect(screen.getByRole("combobox", { name: /cenário de memória/i })).toHaveValue("normal");
    expect(await screen.findByText("OCIOSO")).toBeVisible();
  });

  it.each(["A", "Z", "0", "9", " "])("accepts the supported input %j without normalization", async (value) => {
    render(<App />);
    await screen.findByText("OCIOSO");
    const input = screen.getByRole("textbox", { name: /caractere de entrada/i });

    fireEvent.change(input, { target: { value } });

    expect(input).toHaveValue(value);
    expect(screen.getByRole("button", { name: /iniciar simulação/i })).toBeEnabled();
  });

  it.each(["", "AB", "a", "á", "!"])("rejects unsupported input %j", async (value) => {
    render(<App />);
    await screen.findByText("OCIOSO");
    const input = screen.getByRole("textbox", { name: /caractere de entrada/i });

    fireEvent.change(input, { target: { value } });

    expect(screen.getByRole("button", { name: /iniciar simulação/i })).toBeDisabled();
  });

  it.each([
    ["400", "Entrada inválida para a simulação."],
    ["409", "Já existe uma simulação ativa."],
  ])("shows a useful API error for HTTP %s", async (status, message) => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(statusIdle())
        .mockResolvedValueOnce(
          response({ erro: status === "409" ? message : "Entrada inválida para a simulação." }, Number(status)),
        ),
    );
    render(<App />);
    await screen.findByText("OCIOSO");
    fireEvent.change(screen.getByRole("textbox", { name: /caractere de entrada/i }), {
      target: { value: "A" },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar simulação/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("starts, pauses, resumes, and steps only when the FSM allows it", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(statusIdle())
      .mockResolvedValueOnce(response({
        mensagem: "Simulação iniciada.",
        estado_fsm: "RODANDO",
        sessao_id: "session-1",
        timestamp_inicio: "2026-10-17T10:00:00Z",
      }))
      .mockResolvedValueOnce(response({
        mensagem: "Simulação pausada.",
        estado_fsm: "PAUSADO",
        sessao_id: "session-1",
        sequencia_evento: 2,
        evento: eventPayload("MicrocontroladorTeclado", { status_fsm: "PAUSADO" }),
      }))
      .mockResolvedValueOnce(response({ mensagem: "Simulação retomada.", estado_fsm: "RODANDO" }))
      .mockResolvedValueOnce(response({
        mensagem: "Simulação pausada.",
        estado_fsm: "PAUSADO",
        sessao_id: "session-1",
        sequencia_evento: 3,
        evento: eventPayload("CaboConexao", { status_fsm: "PAUSADO" }),
      }))
      .mockResolvedValueOnce(response({
        mensagem: "Transição concluída.",
        estado_fsm: "PAUSADO",
        sessao_id: "session-1",
        sequencia_evento: 4,
        evento: eventPayload("PortaFisica", { status_fsm: "PAUSADO" }),
      }));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await screen.findByText("OCIOSO");

    const start = screen.getByRole("button", { name: /iniciar simulação/i });
    expect(screen.getByRole("button", { name: "Pausar" })).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: /caractere de entrada/i }), {
      target: { value: "A" },
    });
    fireEvent.click(start);
    await waitFor(() => expect(screen.getByText("RODANDO")).toBeVisible());
    expect(screen.getByRole("button", { name: "Pausar" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Retomar" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Pausar" }));
    await waitFor(() => expect(screen.getByText("PAUSADO")).toBeVisible());
    expect(screen.getByText("Simulação pausada.")).toBeVisible();
    expect(screen.getAllByText("MicrocontroladorTeclado").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Avançar uma etapa" })).toBeEnabled();

    act(() => {
      EventSourceMock.instances[0].emit(
        "session-1:1",
        event("MatrizContatos", 1, { status_fsm: "RODANDO" }),
      );
    });
    expect(screen.getByText(/"exemplo": "MicrocontroladorTeclado"/)).toBeVisible();
    expect(screen.getAllByText("MatrizContatos").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Retomar" }));
    await waitFor(() => expect(screen.getByText("RODANDO")).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "Pausar" }));
    await waitFor(() => expect(screen.getByText("PAUSADO")).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "Avançar uma etapa" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
    expect(screen.getAllByText("PortaFisica").length).toBeGreaterThan(0);
    expect(fetchMock.mock.calls.map(([url, options]) => [url, options?.method])).toEqual([
      ["/api/simulacao/status", undefined],
      ["/api/simulacao/iniciar", "POST"],
      ["/api/simulacao/pause", "POST"],
      ["/api/simulacao/resume", "POST"],
      ["/api/simulacao/pause", "POST"],
      ["/api/simulacao/step", "POST"],
    ]);
  });

  it("sends the chosen scenario and exact character in the start request", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(statusIdle())
      .mockResolvedValueOnce(response({
        mensagem: "Simulação iniciada.",
        estado_fsm: "RODANDO",
        sessao_id: "session-1",
        timestamp_inicio: "2026-10-17T10:00:00Z",
      }));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await screen.findByText("OCIOSO");
    fireEvent.change(screen.getByRole("textbox", { name: /caractere de entrada/i }), {
      target: { value: "Z" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: /cenário de memória/i }), {
      target: { value: "page_fault" },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar simulação/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][0]).toBe("/api/simulacao/iniciar");
    expect(fetchMock.mock.calls[1][1]?.body).toBe(JSON.stringify({
      tecla_entrada: "Z",
      cenario_memoria: "page_fault",
    }));
  });

  it("renders journey snapshots in sequence and ignores duplicate SSE replay", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<App />);
    await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1));
    const source = EventSourceMock.instances[0];
    const first = event("MatrizContatos", 1, { modulo_atual: "Nascimento do dado" });
    const second = event("MicrocontroladorTeclado", 2, { modulo_atual: "Nascimento do dado" });

    act(() => {
      source.emit("session-1:1", first);
      source.emit("session-1:1", first);
      source.emit("session-1:2", second);
    });
    expect((await screen.findAllByText("MatrizContatos")).length).toBeGreaterThan(0);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getAllByText("MicrocontroladorTeclado").length).toBeGreaterThan(0);
    const eventList = within(screen.getByRole("region", { name: /eventos recebidos/i })).getByRole(
      "list",
    );
    expect(within(eventList).getAllByText("Ação em MatrizContatos")).toHaveLength(1);
    expect(within(eventList).getAllByText("Ação em MicrocontroladorTeclado")).toHaveLength(1);
    expect(screen.getByText("Nascimento do dado")).toBeVisible();
    expect(screen.getByText(/"exemplo": "MicrocontroladorTeclado"/)).toBeVisible();
  });

  it("buffers out-of-order sequence numbers and presents them in order", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<App />);
    await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1));
    const source = EventSourceMock.instances[0];

    act(() => {
      source.emit("session-1:2", event("MicrocontroladorTeclado", 2));
    });
    expect(screen.getByText(/0 eventos apresentados/)).toBeVisible();

    act(() => {
      source.emit("session-1:1", event("MatrizContatos", 1));
    });
    expect((await screen.findAllByText("MatrizContatos")).length).toBeGreaterThan(0);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(screen.getAllByText("MicrocontroladorTeclado").length).toBeGreaterThan(0);
  });

  it("synchronizes status after SSE disconnect without sending a stop or pause", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(statusIdle())
      .mockResolvedValueOnce(response({
        sessao_id: "session-1",
        estado_fsm: "PAUSADO",
        modulo_atual: "I/O",
        componente_atual: "Chipset",
        timestamp_ultima_acao: "2026-10-17T10:00:00Z",
      }));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1));

    act(() => EventSourceMock.instances[0].onerror?.());

    expect(await screen.findByText("PAUSADO")).toBeVisible();
    expect(screen.getAllByText("Chipset").length).toBeGreaterThan(0);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/simulacao/status",
      "/api/simulacao/status",
    ]);
    expect(EventSourceMock.instances[0].close).not.toHaveBeenCalled();
  });

  it("shows connection problems while keeping the simulation status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /não foi possível consultar o estado/i,
    );
    expect(EventSourceMock.instances[0].close).not.toHaveBeenCalled();
  });

  it("renders terminal Page Fault and normal completion distinctly", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<App />);
    await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1));
    const source = EventSourceMock.instances[0];

    act(() => {
      for (let sequence = 1; sequence < 11; sequence += 1) {
        source.emit(
          `session-1:${sequence}`,
          event(`Componente${sequence}`, sequence, {
            modulo_atual: sequence < 10 ? "I/O" : "Sistema Operacional",
          }),
        );
      }
      source.emit(
        "session-1:11",
        event("GerenciadorMemoria", 11, {
          status_fsm: "FINALIZADO",
          modulo_atual: "Memória",
          tipo_evento: "ERRO",
          acao_executada: "Page Fault fatal antes da alocação do buffer",
          estado_do_dado: { page_fault: true, buffer_alocado: false },
        }),
      );
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000 * 11);
    });
    expect(screen.getAllByText(/Page Fault fatal/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Resultado: erro")).toBeVisible();
    expect(screen.getByText(/"buffer_alocado": false/)).toBeVisible();

    act(() => {
      source.emit(
        "session-2:1",
        event("ControladorPHY", 1, {
          sessao_id: "session-2",
          status_fsm: "FINALIZADO",
          modulo_atual: "Saída Física",
          tipo_evento: "FINALIZACAO",
          acao_executada: "PHY concluiu a transmissão simulada",
        }),
      );
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(await screen.findByText("Resultado: sucesso")).toBeVisible();
    expect(screen.getByText("Saída Física")).toBeVisible();
  });

  it("keeps the presentation speed fixed without changing API commands", async () => {
    render(<App />);
    const speed = screen.getByRole("slider", { name: /velocidade visual/i });
    expect(speed).toHaveValue("1000");
    expect(speed).toBeDisabled();
    expect(screen.getByText("1000 ms")).toBeVisible();
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
  });

  it("renders the complete eight-phase component map and responsive landmarks", () => {
    render(<App />);
    const journey = screen.getByRole("region", { name: /jornada do dado/i });
    expect(within(journey).getAllByRole("heading", { level: 3 })).toHaveLength(8);
    expect(within(journey).getByText("MicrocontroladorTeclado")).toBeVisible();
    expect(within(journey).getByText("GerenciadorMemoria")).toBeVisible();
    expect(within(journey).getByText("ControladorPHY")).toBeVisible();
    expect(screen.getByRole("region", { name: /estado do dado/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /eventos recebidos/i })).toBeInTheDocument();
  });
});
