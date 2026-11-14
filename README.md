# ArchPath

ArchPath é um simulador didático e interativo que acompanha a jornada de um
caractere desde a entrada no teclado até uma saída de rede representada dentro
do próprio simulador. A interface apresenta as fases, os componentes, o estado
do dado e os eventos produzidos em cada transição.

> **Importante:** a etapa de rede é somente uma simulação pedagógica. O ArchPath
> não envia pacotes para outros computadores nem para a Internet.

Este guia parte de um computador sem ferramentas de desenvolvimento instaladas
e leva da instalação dos requisitos até iniciar e usar a aplicação. Não é
necessário instalar Python, Node.js, npm, bibliotecas do projeto nem Chromium no
computador: o Docker executa esses componentes em containers.

## 1. O que você precisa

- Um computador com Windows 10/11 de 64 bits, macOS ou uma distribuição Linux
  compatível com Docker.
- Conexão com a Internet durante a instalação e a primeira inicialização, para
  baixar o código e as imagens da aplicação.
- Um navegador atualizado. Se não houver nenhum instalado, use a página oficial
  do [Chrome](https://www.google.com/chrome/), [Firefox](https://www.mozilla.org/firefox/new/),
  [Edge](https://www.microsoft.com/edge/download) ou [Safari](https://www.apple.com/safari/).
- Espaço livre em disco para instalar o Docker e baixar as imagens Docker.
- **Git** para clonar o repositório. Se preferir, é possível baixar o projeto
  como ZIP (instruções abaixo).
- **Docker Engine e Docker Compose v2**. No Windows e no macOS, a forma mais
  simples é instalar Docker Desktop, que inclui os dois.

## 2. Instalar as ferramentas

### Windows

1. Instale o Git for Windows em <https://git-scm.com/download/win>. Durante a
   instalação, as opções padrão são suficientes.
2. Instale o Docker Desktop em <https://docs.docker.com/desktop/setup/install/windows-install/>.
   Siga o instalador e habilite o backend WSL 2 quando solicitado. Se o
   instalador pedir para habilitar ou atualizar o WSL, siga as instruções
   exibidas e reinicie o computador.
3. Abra o Docker Desktop pelo menu Iniciar e aguarde ele indicar que o Docker
   está em execução.
4. Abra **Git Bash** pelo menu Iniciar para executar os comandos deste guia.
   Também é possível usar uma distribuição Linux instalada no WSL.

### macOS

1. Instale o Git. Se já tiver as ferramentas de linha de comando do Xcode,
   provavelmente já está instalado. Caso contrário, instale o Xcode Command Line
   Tools com `xcode-select --install` no Terminal ou instale o Git em
   <https://git-scm.com/download/mac>.
2. Instale Docker Desktop para o seu tipo de processador (Apple Silicon ou
   Intel) seguindo <https://docs.docker.com/desktop/setup/install/mac-install/>.
3. Abra Docker Desktop pela pasta **Applications** e aguarde a confirmação de
   que o Docker está em execução.
4. Abra o aplicativo **Terminal**.

### Linux

1. Instale o Git pelo gerenciador de pacotes da sua distribuição. Por exemplo,
   em Ubuntu ou Debian:

   ```sh
   sudo apt update
   sudo apt install git
   ```

2. Instale **Docker Engine** e o **plugin Docker Compose** seguindo a
   documentação oficial correspondente à sua distribuição:
   <https://docs.docker.com/engine/install/>.
   A instalação deve disponibilizar os comandos `docker` e
   `docker compose` (Compose v2).
3. Inicie e habilite o serviço Docker conforme as instruções da distribuição.
   Se o comando `docker` exigir privilégios administrativos, configure o acesso
   do seu usuário seguindo a documentação do Docker; depois, encerre e reabra a
   sessão. A alternativa é executar os comandos Docker com `sudo`.
4. Abra um Terminal.

> Os nomes de menus e as etapas de instalação podem variar conforme a versão do
> sistema operacional e a distribuição Linux. Use sempre a documentação oficial
> indicada acima.

### Confirmar a instalação

Abra um terminal (Git Bash/WSL no Windows) e execute:

```sh
git --version
docker --version
docker compose version
```

Os três comandos devem mostrar suas versões. No Windows/macOS, confirme também
que o Docker Desktop está aberto. No Linux, confirme que o serviço Docker está
ativo. Se `docker compose version` não funcionar, instale ou atualize o plugin
Compose v2 seguindo as instruções oficiais para seu sistema.

## 3. Baixar o ArchPath

Escolha uma das opções.

### Opção A — Clonar com Git

No terminal, navegue até a pasta onde deseja guardar o projeto e execute:

```sh
git clone https://github.com/carlos-douglas-pessoal/ArchPath.git
cd ArchPath
```

### Opção B — Baixar como ZIP

1. Abra <https://github.com/carlos-douglas-pessoal/ArchPath>.
2. Selecione **Code → Download ZIP** e extraia o arquivo.
3. Abra um terminal e entre na pasta extraída, que normalmente se chama
   `ArchPath`:

   ```sh
   cd ArchPath
   ```

Os comandos seguintes devem ser executados **na raiz do projeto** — a pasta que
contém `compose.yaml`.

## 4. Iniciar a aplicação

1. Confirme que o Docker está em execução.
2. No terminal, já dentro da pasta `ArchPath`, execute:

   ```sh
   docker compose up --build
   ```

3. Na primeira execução, o Docker baixa as imagens necessárias e constrói os
   serviços. Isso pode levar alguns minutos. As mensagens dos serviços aparecem
   no terminal; mantenha essa janela aberta enquanto estiver usando a aplicação.
4. Quando o frontend e o backend estiverem prontos, abra no navegador:
   **<http://127.0.0.1:5173>**.

O backend disponibiliza a API em <http://127.0.0.1:8000>, a documentação
interativa da API em <http://127.0.0.1:8000/docs> e o endereço de saúde em
<http://127.0.0.1:8000/healthz>. Para usar o simulador, basta abrir a interface
na porta 5173.

As portas são publicadas somente no próprio computador (`127.0.0.1`); outros
dispositivos da rede não conseguem acessá-las por padrão.

### Deixar os serviços em segundo plano (opcional)

Se quiser liberar o terminal depois de iniciar os serviços, pare a execução
com `Ctrl+C` e inicie-os em segundo plano:

```sh
docker compose up --build -d
```

Confira se os serviços estão prontos:

```sh
docker compose ps
```

Quando a coluna de estado indicar `healthy`, abra ou atualize
<http://127.0.0.1:5173>. Para ver as mensagens de execução:

```sh
docker compose logs -f
```

Saia da visualização dos logs com `Ctrl+C`; isso não para os containers quando
eles foram iniciados em segundo plano.

## 5. Usar o simulador

Na página do ArchPath, a área **Configure e acompanhe** permite iniciar e
controlar uma jornada.

### Iniciar uma jornada normal

1. Em **Caractere de entrada**, informe exatamente um caractere: uma letra
   maiúscula (`A`–`Z`), um algarismo (`0`–`9`) ou um espaço.
2. Em **Cenário de memória**, escolha **Normal — jornada completa**.
3. Selecione **Iniciar simulação**.
4. Acompanhe o estado da sessão, a fase atual, o componente em execução, o
   snapshot do dado e a lista de eventos recebidos.

A jornada normal percorre, nesta ordem:

1. **Nascimento do dado** — contatos da tecla, microcontrolador e conexão.
2. **I/O** — porta, interface, chipset, interrupção e barramento.
3. **CPU** — atendimento e processamento da entrada.
4. **Sistema Operacional** — tradução da entrada pelo driver.
5. **Memória** — tradução de endereços e alocação temporária.
6. **DMA** — transferência do dado sem ciclos simulados da CPU para essa etapa.
7. **Rede** — representação didática do encapsulamento e dos componentes de
   rede.
8. **Saída Física** — representação da saída pelo controlador PHY.

O cenário normal produz 21 eventos de componente e termina com o resultado
**sucesso**. A aplicação retorna ao estado `OCIOSO` depois de liberar a sessão.

### Experimentar o cenário Page Fault

1. Informe um caractere válido.
2. Em **Cenário de memória**, escolha **Page Fault — falha fatal**.
3. Selecione **Iniciar simulação**.

Esse cenário termina com o resultado **erro** ao detectar a falha de página. É
intencionalmente fatal: não há recuperação, nova tentativa, alocação do buffer
nem continuação para DMA ou rede. Para continuar usando o simulador, inicie uma
nova sessão depois que a anterior terminar.

### Pausar, avançar e retomar

- **Pausar** interrompe a jornada depois da transição em andamento.
- **Avançar uma etapa** só fica disponível quando a sessão está pausada; executa
  uma única transição de componente e volta a pausar. Uma etapa não corresponde
  a uma fase inteira.
- **Retomar** continua a jornada automaticamente até a próxima pausa ou o fim.
- O indicador no topo mostra estados como `OCIOSO`, `RODANDO`, `PAUSADO` e
  `FINALIZADO`. Os controles incompatíveis com o estado atual ficam
  desabilitados.

### Apresentação e leitura dos detalhes

- **Velocidade visual** está fixada em `1000 ms` entre os eventos apresentados
  na interface; o controle aparece desabilitado.
- Esse intervalo ajusta somente a apresentação no navegador. O motor da
  simulação mantém seu próprio ritmo; portanto, a velocidade visual não altera
  a execução interna.
- **Jornada do dado** destaca a fase e o componente atuais.
- **Estado do dado** mostra o snapshot e a ação do componente que gerou o evento
  mais recente.
- **Eventos recebidos** lista as transições com sequência, componente, ação e
  tipo de evento.
- O indicador de conexão informa se o navegador está conectado ao fluxo de
  eventos ou tentando reconectar. Uma perda momentânea da conexão pode afetar a
  atualização visual; a interface tenta sincronizar o estado novamente.

### Limites de sessões

Esta versão permite somente **uma sessão ativa por processo de backend**. Se
houver uma sessão em andamento, outra tentativa de iniciar será recusada.
Espere a sessão terminar antes de iniciar outra. Sessões e eventos ficam em
memória e são apagados quando o backend é reiniciado ou os containers são
recriados.

## 6. Parar e iniciar novamente

Se os serviços estiverem em primeiro plano, pressione `Ctrl+C` no terminal que
está executando o Compose. Em seguida, na raiz do projeto, remova os containers
e a rede criados pelo ArchPath:

```sh
docker compose down
```

Esse comando não desinstala Docker nem apaga os arquivos do projeto. Para iniciar
novamente, repita:

```sh
docker compose up --build
```

Para uma inicialização posterior sem reconstruir as imagens:

```sh
docker compose up
```

Use `docker compose down` também para parar os serviços que foram iniciados com
`-d`.

## 7. Solução de problemas

### O navegador não abre a página

- Confirme que Docker Desktop está aberto (Windows/macOS) ou que o serviço
  Docker está ativo (Linux).
- Confira `docker compose ps` e aguarde os serviços ficarem `healthy`.
- Confirme que abriu <http://127.0.0.1:5173>, não a porta da API (`8000`).
- Veja os logs com `docker compose logs -f`.
- Se os containers pararam ou falharam, volte ao terminal e execute
  `docker compose up --build`.

### A porta já está em uso

Se o Docker informar que as portas `5173` ou `8000` já estão ocupadas, feche o
outro programa que as utiliza e tente novamente. Não altere as portas sem
atualizar também a configuração e o proxy da aplicação.

### O comando Docker não consegue conectar ao daemon

- No Windows/macOS, abra Docker Desktop e aguarde a inicialização completa.
- No Linux, inicie o serviço Docker. Se seu usuário não tiver permissão para
  acessar o daemon, siga as instruções de instalação do Docker Engine ou use
  `sudo` nos comandos Docker.

### Quero começar de uma instalação limpa

Pare o projeto com `docker compose down` e inicie novamente com
`docker compose up --build`. Isso reconstrói os serviços a partir dos arquivos
do projeto. A sessão e o histórico já são temporários e não são persistidos.

## 8. Executar os testes (opcional)

Os testes são úteis para quem está desenvolvendo ou quer verificar a instalação.
Eles não são necessários para simplesmente usar a interface. Na raiz do projeto,
execute:

```sh
sh scripts/test-compose.sh
```

O script constrói e inicia backend e frontend, executa os testes de scaffold,
backend e integração HTTP/SSE pela rede Docker, reinicia o backend para verificar
que sessões/histórico não persistem, roda os testes do frontend e os fluxos
Playwright/Chromium em containers. Se uma etapa falhar, o script termina com
código de erro. Ao concluir com sucesso, backend e frontend permanecem em
execução para que você possa abrir o simulador; use `docker compose down` quando
terminar.

No Windows, execute esse comando em **Git Bash** ou em um terminal WSL. No
macOS/Linux, use o Terminal.

As verificações estáticas e de configuração utilizadas pelo CI podem ser
executadas separadamente:

```sh
docker compose config --quiet
docker compose --profile test run --build --rm backend-tests \
  sh -c 'ruff check app tests && ruff format --check app tests'
docker compose --profile test run --build --rm frontend-tests \
  sh -c 'npm run lint && npm run build'
```

O workflow do GitHub Actions executa essas verificações e duas regressões
completas em cada push e pull request. A exigência desse check para permitir
merge depende da configuração de proteção da branch no GitHub.

## 9. Arquitetura e limitações

- **Frontend:** React, TypeScript e Vite.
- **Backend:** Python, FastAPI e Uvicorn.
- **Atualização dos eventos:** Server-Sent Events (SSE).
- **Execução:** Docker Compose v2; não requer Python, Node.js ou navegador
  automatizado instalados no host.
- **Sessões:** uma sessão ativa em memória por processo; sem banco de dados,
  broker, persistência ou múltiplas réplicas.
- **Segurança de rede:** as portas do host são vinculadas a `127.0.0.1`.
- **Uso:** aplicação demonstrativa local; não implementa autenticação ou
  autorização e não foi projetada para exposição direta à Internet.
- **Rede simulada:** os endereços, protocolos, quadros e valores apresentados
  são ilustrações pedagógicas. Nenhum tráfego é transmitido externamente.
