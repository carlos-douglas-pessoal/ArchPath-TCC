from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TypedDict
from uuid import UUID, uuid4


class InvalidSimulationInput(ValueError):
    """Raised when a simulation request is outside the supported domain."""


class MemoryScenario(StrEnum):
    NORMAL = "normal"
    PAGE_FAULT = "page_fault"


class SimulationState(StrEnum):
    RUNNING = "RODANDO"
    PAUSED = "PAUSADO"
    WAITING_STEP = "AGUARDANDO_STEP"
    FINISHED = "FINALIZADO"


class JourneyPhase(StrEnum):
    DATA_BIRTH = "Nascimento do dado"
    IO = "I/O"
    CPU = "CPU"
    OPERATING_SYSTEM = "Sistema Operacional"
    MEMORY = "Memória"
    DMA = "DMA"
    NETWORK = "Rede"
    PHYSICAL_OUTPUT = "Saída Física"


class JourneyComponent(StrEnum):
    CONTACT_MATRIX = "MatrizContatos"
    KEYBOARD_CONTROLLER = "MicrocontroladorTeclado"
    CONNECTION_CABLE = "CaboConexao"
    PHYSICAL_PORT = "PortaFisica"
    INTERFACE_CONTROLLER = "ControladorInterface"
    CHIPSET = "Chipset"
    APIC = "APIC"
    SYSTEM_BUS = "BarramentoSistema"
    CPU_CONTROL_UNIT = "UnidadeControle"
    KEYBOARD_DRIVER = "DriverTecladoOS"
    MEMORY_MANAGER = "GerenciadorMemoria"
    TEMPORARY_BUFFER = "BufferTemporario"
    DMA_CONTROLLER = "ControladorDMA"
    APPLICATION_LAYER = "L7_Aplicacao"
    PRESENTATION_LAYER = "L6_Apresentacao"
    SESSION_LAYER = "L5_Sessao"
    TRANSPORT_LAYER = "L4_Transporte"
    NETWORK_LAYER = "L3_Rede"
    MAC_CONTROLLER = "ControladorMAC"
    NETWORK_FIFO = "SRAM"
    PHY_CONTROLLER = "ControladorPHY"


class SimulationEventType(StrEnum):
    TRANSITION = "TRANSICAO"
    ERROR = "ERRO"
    FINALIZATION = "FINALIZACAO"


class SimulationData(TypedDict, total=False):
    tecla_entrada: str
    scancode: str
    scancode_gerado: str
    scancode_recebido: str
    protocolo_periferico: str
    protocolo_transmissao: str
    circuito_fechado: bool
    linha_ativa: int
    coluna_ativa: int
    variacao_tensao: str
    pulsos_diferenciais: bool
    pulsos_recebidos: bool
    porta_conectada: bool
    interface_decodificada: bool
    dado_retido_no_chipset: bool
    chipset_ocupado: bool
    irq_levantada: bool
    irq_prioridade: int
    dado_no_barramento_sistema: bool
    via_liberada: bool
    interrupcao_atendida: bool
    registradores: dict[str, str]
    cpu_ciclos_simulados: int
    driver_assumiu_controle: bool
    caractere_traduzido: str
    endereco_virtual: str
    endereco_fisico: str
    pagina_mapeada: bool
    page_fault: bool
    buffer_alocado: bool
    buffer_endereco_inicio: str
    buffer_endereco_fim: str
    dma_executado: bool
    dma_leu_buffer: bool
    dma_usou_cpu: bool
    barramento_expansao: str
    payload_rede: str
    protocolo_aplicacao: str
    dados_codificados: bool
    formato_codificacao: str
    sessao_rede_estabelecida: bool
    id_sessao_rede: str
    cabecalhos: list[str]
    transporte: str
    porta_origem: int
    porta_destino: int
    ip_origem: str
    ip_destino: str
    mac_origem: str
    mac_destino: str
    quadro_ethernet: bool
    fila_fifo: list[str]
    fifo_liberada: bool
    quadros_na_fila: int
    phy_conversao_concluida: bool
    sinais_phy: str
    transmissao_externa: bool


@dataclass(slots=True)
class SimulationSession:
    session_id: UUID
    input_character: str
    scancode: str
    scenario: MemoryScenario
    state: SimulationState
    started_at: datetime
    last_action_at: datetime
    data: SimulationData = field(default_factory=dict)
    transition_index: int = 0
    current_phase: JourneyPhase | None = None
    current_component: JourneyComponent | None = None

    @classmethod
    def create(
        cls,
        character: str,
        scenario: MemoryScenario | str = MemoryScenario.NORMAL,
    ) -> "SimulationSession":
        if not isinstance(character, str) or len(character) != 1:
            raise InvalidSimulationInput(
                "A entrada deve ser uma letra maiúscula, um algarismo ou espaço."
            )

        try:
            memory_scenario = MemoryScenario(scenario)
        except (TypeError, ValueError) as error:
            raise InvalidSimulationInput("Cenário de memória desconhecido.") from error

        scancode = _SCANCODES.get(character)
        if scancode is None:
            raise InvalidSimulationInput(
                "A entrada deve ser uma letra maiúscula, um algarismo ou espaço."
            )

        now = datetime.now(UTC)
        return cls(
            session_id=uuid4(),
            input_character=character,
            scancode=scancode,
            scenario=memory_scenario,
            state=SimulationState.RUNNING,
            started_at=now,
            last_action_at=now,
            data={
                "tecla_entrada": character,
                "buffer_alocado": False,
            },
        )

    @property
    def is_terminal(self) -> bool:
        return self.state is SimulationState.FINISHED

    def data_snapshot(self) -> SimulationData:
        return deepcopy(self.data)


_SCANCODES = {
    "A": "0x1E",
    "B": "0x30",
    "C": "0x2E",
    "D": "0x20",
    "E": "0x12",
    "F": "0x21",
    "G": "0x22",
    "H": "0x23",
    "I": "0x17",
    "J": "0x24",
    "K": "0x25",
    "L": "0x26",
    "M": "0x32",
    "N": "0x31",
    "O": "0x18",
    "P": "0x19",
    "Q": "0x10",
    "R": "0x13",
    "S": "0x1F",
    "T": "0x14",
    "U": "0x16",
    "V": "0x2F",
    "W": "0x11",
    "X": "0x2D",
    "Y": "0x15",
    "Z": "0x2C",
    "1": "0x02",
    "2": "0x03",
    "3": "0x04",
    "4": "0x05",
    "5": "0x06",
    "6": "0x07",
    "7": "0x08",
    "8": "0x09",
    "9": "0x0A",
    "0": "0x0B",
    " ": "0x39",
}


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    timestamp: datetime
    session_id: UUID
    state: SimulationState
    phase: JourneyPhase
    component: JourneyComponent
    action: str
    event_type: SimulationEventType
    data_snapshot: SimulationData
    terminal_result: str | None = None

    @property
    def snapshot(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "sessao_id": str(self.session_id),
            "status_fsm": self.state.value,
            "modulo_atual": self.phase.value,
            "componente_atual": self.component.value,
            "tipo_evento": self.event_type.value,
            "acao_executada": self.action,
            "estado_do_dado": deepcopy(self.data_snapshot),
        }
