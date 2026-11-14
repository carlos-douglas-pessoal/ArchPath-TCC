from string import ascii_uppercase, digits
from uuid import UUID

import pytest

from app.domain.journey import Journey
from app.domain.models import (
    InvalidSimulationInput,
    JourneyComponent,
    JourneyPhase,
    MemoryScenario,
    SimulationEvent,
    SimulationSession,
    SimulationState,
)

EXPECTED_SCANCODES = {
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


@pytest.mark.parametrize(
    ("character", "scancode"),
    [
        ("A", "0x1E"),
        ("Z", "0x2C"),
        ("0", "0x0B"),
        ("1", "0x02"),
        (" ", "0x39"),
    ],
)
def test_session_maps_supported_logical_input_to_set_one_scancode(
    character: str,
    scancode: str,
) -> None:
    session = SimulationSession.create(character)

    assert session.data["tecla_entrada"] == character
    assert session.scancode == scancode
    assert session.scenario is MemoryScenario.NORMAL
    assert session.state is SimulationState.RUNNING


@pytest.mark.parametrize("character", ["", "a", "é", "!", "AB", "\n", "Ａ"])
def test_session_rejects_unsupported_logical_input(character: str) -> None:
    with pytest.raises(InvalidSimulationInput):
        SimulationSession.create(character)


def test_session_rejects_unknown_memory_scenario() -> None:
    with pytest.raises(InvalidSimulationInput):
        SimulationSession.create("A", scenario="swap")


def test_all_supported_ascii_inputs_have_a_didactic_scancode() -> None:
    assert set(EXPECTED_SCANCODES) == set(ascii_uppercase + digits + " ")
    assert {
        character: SimulationSession.create(character).scancode for character in EXPECTED_SCANCODES
    } == EXPECTED_SCANCODES


def test_journey_exposes_the_complete_ordered_component_sequence() -> None:
    assert Journey.components == (
        JourneyComponent.CONTACT_MATRIX,
        JourneyComponent.KEYBOARD_CONTROLLER,
        JourneyComponent.CONNECTION_CABLE,
        JourneyComponent.PHYSICAL_PORT,
        JourneyComponent.INTERFACE_CONTROLLER,
        JourneyComponent.CHIPSET,
        JourneyComponent.APIC,
        JourneyComponent.SYSTEM_BUS,
        JourneyComponent.CPU_CONTROL_UNIT,
        JourneyComponent.KEYBOARD_DRIVER,
        JourneyComponent.MEMORY_MANAGER,
        JourneyComponent.TEMPORARY_BUFFER,
        JourneyComponent.DMA_CONTROLLER,
        JourneyComponent.APPLICATION_LAYER,
        JourneyComponent.PRESENTATION_LAYER,
        JourneyComponent.SESSION_LAYER,
        JourneyComponent.TRANSPORT_LAYER,
        JourneyComponent.NETWORK_LAYER,
        JourneyComponent.MAC_CONTROLLER,
        JourneyComponent.NETWORK_FIFO,
        JourneyComponent.PHY_CONTROLLER,
    )


def test_transition_returns_a_typed_event_with_uuid_and_timezone_aware_timestamp() -> None:
    event = Journey().advance(SimulationSession.create("A"))

    assert isinstance(event, SimulationEvent)
    assert isinstance(event.session_id, UUID)
    assert event.timestamp.tzinfo is not None
    assert event.snapshot["sessao_id"] == str(event.session_id)
    assert event.snapshot["status_fsm"] == "RODANDO"


def test_normal_journey_advances_one_component_and_returns_post_action_snapshots() -> None:
    session = SimulationSession.create("A")
    journey = Journey()
    results = []
    snapshots = []

    while not session.is_terminal:
        result = journey.advance(session)
        results.append(result)
        snapshots.append(result.snapshot)

    assert [snapshot["componente_atual"] for snapshot in snapshots] == [
        component.value for component in Journey.components
    ]
    assert all(snapshot["status_fsm"] == "RODANDO" for snapshot in snapshots[:-1])
    assert snapshots[-1]["status_fsm"] == "FINALIZADO"
    assert snapshots[-1]["tipo_evento"] == "FINALIZACAO"
    assert tuple(dict.fromkeys(result.phase for result in results)) == tuple(JourneyPhase)
    assert snapshots[-1]["estado_do_dado"]["sinais_phy"] == "sinais_fisicos_simulados"
    assert session.state is SimulationState.FINISHED
    assert session.data["caractere_traduzido"] == "A"
    assert session.data["endereco_virtual"] == "0x1000"
    assert session.data["endereco_fisico"] == "0x1A2B"
    assert session.data["buffer_alocado"] is True
    assert session.data["dma_usou_cpu"] is False
    assert session.data["cabecalhos"] == ["UDP", "IP"]
    assert session.data["quadro_ethernet"] is True
    assert len(snapshots) == len(Journey.components)


def test_page_fault_is_terminal_before_buffer_dma_or_network() -> None:
    session = SimulationSession.create("A", MemoryScenario.PAGE_FAULT)
    journey = Journey()

    results = []
    while not session.is_terminal:
        results.append(journey.advance(session))

    terminal = results[-1]
    assert terminal.component is JourneyComponent.MEMORY_MANAGER
    assert terminal.phase is JourneyPhase.MEMORY
    assert terminal.snapshot["status_fsm"] == "FINALIZADO"
    assert terminal.snapshot["tipo_evento"] == "ERRO"
    assert session.state is SimulationState.FINISHED
    assert session.data["page_fault"] is True
    assert session.data["buffer_alocado"] is False
    assert not session.data.get("dma_executado", False)
    assert not session.data.get("cabecalhos")
    assert all(
        result.component
        not in {
            JourneyComponent.DMA_CONTROLLER,
            JourneyComponent.APPLICATION_LAYER,
            JourneyComponent.PRESENTATION_LAYER,
            JourneyComponent.SESSION_LAYER,
            JourneyComponent.TRANSPORT_LAYER,
            JourneyComponent.NETWORK_LAYER,
            JourneyComponent.MAC_CONTROLLER,
            JourneyComponent.NETWORK_FIFO,
            JourneyComponent.PHY_CONTROLLER,
        }
        for result in results
    )
    with pytest.raises(InvalidSimulationInput, match="encerrada"):
        journey.advance(session)


def test_snapshots_do_not_change_when_later_transitions_mutate_session() -> None:
    session = SimulationSession.create("B")
    journey = Journey()

    first_snapshot = journey.advance(session).snapshot
    journey.advance(session)

    assert first_snapshot["componente_atual"] == JourneyComponent.CONTACT_MATRIX.value
    assert first_snapshot["estado_do_dado"]["circuito_fechado"] is True
    assert "scancode" not in first_snapshot["estado_do_dado"]
