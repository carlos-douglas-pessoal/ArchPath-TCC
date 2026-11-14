from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.models import (
    InvalidSimulationInput,
    JourneyComponent,
    JourneyPhase,
    SimulationEvent,
    SimulationEventType,
    SimulationSession,
    SimulationState,
)
from app.domain.modules import processors


@dataclass(frozen=True, slots=True)
class _Transition:
    phase: JourneyPhase
    component: JourneyComponent
    action: str
    execute: Callable[[SimulationSession], bool | None]


_TRANSITIONS = (
    _Transition(
        JourneyPhase.DATA_BIRTH,
        JourneyComponent.CONTACT_MATRIX,
        "Circuito da tecla fechado e variação de tensão gerada",
        processors.close_contact_matrix,
    ),
    _Transition(
        JourneyPhase.DATA_BIRTH,
        JourneyComponent.KEYBOARD_CONTROLLER,
        "Scancode didático set 1 gerado",
        processors.generate_scancode,
    ),
    _Transition(
        JourneyPhase.DATA_BIRTH,
        JourneyComponent.CONNECTION_CABLE,
        "Scancode transmitido como pulsos diferenciais didáticos",
        processors.transmit_from_keyboard,
    ),
    _Transition(
        JourneyPhase.IO,
        JourneyComponent.PHYSICAL_PORT,
        "Pulsos recebidos pela porta física",
        processors.receive_at_physical_port,
    ),
    _Transition(
        JourneyPhase.IO,
        JourneyComponent.INTERFACE_CONTROLLER,
        "Sinal recebido e scancode decodificado",
        processors.decode_interface_signal,
    ),
    _Transition(
        JourneyPhase.IO,
        JourneyComponent.CHIPSET,
        "Dado retido temporariamente no chipset",
        processors.retain_in_chipset,
    ),
    _Transition(
        JourneyPhase.IO,
        JourneyComponent.APIC,
        "IRQ levantada para atendimento da CPU",
        processors.raise_apic_interrupt,
    ),
    _Transition(
        JourneyPhase.IO,
        JourneyComponent.SYSTEM_BUS,
        "Dado disponibilizado no barramento do sistema",
        processors.transport_on_system_bus,
    ),
    _Transition(
        JourneyPhase.CPU,
        JourneyComponent.CPU_CONTROL_UNIT,
        "Interrupção atendida e scancode carregado em registrador",
        processors.fetch_into_cpu_register,
    ),
    _Transition(
        JourneyPhase.OPERATING_SYSTEM,
        JourneyComponent.KEYBOARD_DRIVER,
        "Driver traduziu o scancode para o caractere lógico",
        processors.translate_with_keyboard_driver,
    ),
    _Transition(
        JourneyPhase.MEMORY,
        JourneyComponent.MEMORY_MANAGER,
        "Endereço virtual traduzido e mapeamento validado",
        processors.translate_memory_address,
    ),
    _Transition(
        JourneyPhase.MEMORY,
        JourneyComponent.TEMPORARY_BUFFER,
        "Dado alocado no buffer físico da RAM",
        processors.allocate_temporary_buffer,
    ),
    _Transition(
        JourneyPhase.DMA,
        JourneyComponent.DMA_CONTROLLER,
        "DMA leu o buffer sem ciclos simulados da CPU",
        processors.execute_dma_transfer,
    ),
    _Transition(
        JourneyPhase.NETWORK,
        JourneyComponent.APPLICATION_LAYER,
        "Camada de aplicação preparou o payload",
        processors.encapsulate_network_packet,
    ),
    _Transition(
        JourneyPhase.NETWORK,
        JourneyComponent.PRESENTATION_LAYER,
        "Camada de apresentação codificou o payload",
        processors.encode_network_payload,
    ),
    _Transition(
        JourneyPhase.NETWORK,
        JourneyComponent.SESSION_LAYER,
        "Camada de sessão estabeleceu sessão didática",
        processors.establish_network_session,
    ),
    _Transition(
        JourneyPhase.NETWORK,
        JourneyComponent.TRANSPORT_LAYER,
        "Cabeçalho de transporte UDP adicionado",
        processors.add_udp_header,
    ),
    _Transition(
        JourneyPhase.NETWORK,
        JourneyComponent.NETWORK_LAYER,
        "Cabeçalho de rede IP adicionado",
        processors.add_ip_header,
    ),
    _Transition(
        JourneyPhase.NETWORK,
        JourneyComponent.MAC_CONTROLLER,
        "Quadro Ethernet didático enfileirado na FIFO",
        processors.enqueue_ethernet_frame,
    ),
    _Transition(
        JourneyPhase.NETWORK,
        JourneyComponent.NETWORK_FIFO,
        "FIFO liberou o quadro para o PHY",
        processors.release_frame_from_fifo,
    ),
    _Transition(
        JourneyPhase.PHYSICAL_OUTPUT,
        JourneyComponent.PHY_CONTROLLER,
        "PHY converteu o quadro em sinais físicos simulados",
        processors.convert_to_physical_signals,
    ),
)

_ACTIONS_BY_COMPONENT = {
    JourneyComponent.MEMORY_MANAGER: "Page Fault fatal antes da alocação do buffer",
}


class Journey:
    components = tuple(transition.component for transition in _TRANSITIONS)

    def advance(self, session: SimulationSession) -> SimulationEvent:
        if session.is_terminal:
            raise InvalidSimulationInput("A jornada já foi encerrada.")
        if session.transition_index >= len(_TRANSITIONS):
            raise InvalidSimulationInput("A jornada não possui transições restantes.")

        transition = _TRANSITIONS[session.transition_index]
        session.current_phase = transition.phase
        session.current_component = transition.component
        keep_going = transition.execute(session)
        session.transition_index += 1
        session.last_action_at = datetime.now(UTC)

        terminal_result: str | None = None
        event_type = SimulationEventType.TRANSITION
        action = transition.action

        if transition.component is JourneyComponent.MEMORY_MANAGER and not keep_going:
            session.state = SimulationState.FINISHED
            event_type = SimulationEventType.ERROR
            action = _ACTIONS_BY_COMPONENT[transition.component]
            terminal_result = "erro"
        elif session.transition_index == len(_TRANSITIONS):
            session.state = SimulationState.FINISHED
            event_type = SimulationEventType.FINALIZATION
            terminal_result = "sucesso"

        return SimulationEvent(
            timestamp=session.last_action_at,
            session_id=session.session_id,
            state=session.state,
            phase=transition.phase,
            component=transition.component,
            action=action,
            event_type=event_type,
            data_snapshot=session.data_snapshot(),
            terminal_result=terminal_result,
        )
