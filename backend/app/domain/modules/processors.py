from app.domain.models import MemoryScenario, SimulationSession


def close_contact_matrix(session: SimulationSession) -> None:
    session.data.update(
        circuito_fechado=True,
        linha_ativa=2,
        coluna_ativa=3,
        variacao_tensao="5.0V",
    )


def generate_scancode(session: SimulationSession) -> None:
    session.data.update(
        scancode=session.scancode,
        scancode_gerado=session.scancode,
        protocolo_periferico="USB (representação didática)",
    )


def transmit_from_keyboard(session: SimulationSession) -> None:
    session.data.update(
        pulsos_diferenciais=True,
        protocolo_transmissao="USB (representação didática)",
    )


def receive_at_physical_port(session: SimulationSession) -> None:
    session.data.update(pulsos_recebidos=True, porta_conectada=True)


def decode_interface_signal(session: SimulationSession) -> None:
    session.data.update(
        scancode_recebido=session.scancode,
        interface_decodificada=True,
    )


def retain_in_chipset(session: SimulationSession) -> None:
    session.data.update(dado_retido_no_chipset=True, chipset_ocupado=False)


def raise_apic_interrupt(session: SimulationSession) -> None:
    session.data.update(irq_levantada=True, irq_prioridade=1)


def transport_on_system_bus(session: SimulationSession) -> None:
    session.data.update(dado_no_barramento_sistema=True, via_liberada=True)


def fetch_into_cpu_register(session: SimulationSession) -> None:
    session.data.update(
        interrupcao_atendida=True,
        registradores={"RAX": session.scancode},
        cpu_ciclos_simulados=1,
    )


def translate_with_keyboard_driver(session: SimulationSession) -> None:
    session.data.update(
        driver_assumiu_controle=True,
        caractere_traduzido=session.input_character,
    )


def translate_memory_address(session: SimulationSession) -> bool:
    if session.scenario is MemoryScenario.PAGE_FAULT:
        session.data.update(
            endereco_virtual="0xDEAD",
            pagina_mapeada=False,
            page_fault=True,
            buffer_alocado=False,
        )
        return False

    session.data.update(
        endereco_virtual="0x1000",
        endereco_fisico="0x1A2B",
        pagina_mapeada=True,
        page_fault=False,
    )
    return True


def allocate_temporary_buffer(session: SimulationSession) -> None:
    session.data.update(
        buffer_alocado=True,
        buffer_endereco_inicio="0x1A2B",
        buffer_endereco_fim="0x1A2C",
    )


def execute_dma_transfer(session: SimulationSession) -> None:
    session.data.update(
        dma_executado=True,
        dma_leu_buffer=True,
        dma_usou_cpu=False,
        barramento_expansao="PCIe (representação didática)",
    )


def encapsulate_network_packet(session: SimulationSession) -> None:
    session.data.update(
        payload_rede=session.input_character,
        protocolo_aplicacao="mensagem didática",
    )


def encode_network_payload(session: SimulationSession) -> None:
    session.data.update(dados_codificados=True, formato_codificacao="UTF-8 (didático)")


def establish_network_session(session: SimulationSession) -> None:
    session.data.update(sessao_rede_estabelecida=True, id_sessao_rede="sessao-didatica")


def add_udp_header(session: SimulationSession) -> None:
    headers = list(session.data.get("cabecalhos", []))
    headers.append("UDP")
    session.data.update(
        cabecalhos=headers, transporte="UDP", porta_origem=49152, porta_destino=9000
    )


def add_ip_header(session: SimulationSession) -> None:
    headers = list(session.data.get("cabecalhos", []))
    headers.append("IP")
    session.data.update(
        cabecalhos=headers,
        ip_origem="192.0.2.10",
        ip_destino="192.0.2.20",
    )


def enqueue_ethernet_frame(session: SimulationSession) -> None:
    session.data.update(
        mac_origem="02:00:00:00:00:01",
        mac_destino="02:00:00:00:00:02",
        quadro_ethernet=True,
        fila_fifo=["quadro didático"],
    )


def release_frame_from_fifo(session: SimulationSession) -> None:
    session.data.update(fifo_liberada=True, quadros_na_fila=0)


def convert_to_physical_signals(session: SimulationSession) -> None:
    session.data.update(
        phy_conversao_concluida=True,
        sinais_phy="sinais_fisicos_simulados",
        transmissao_externa=False,
    )
