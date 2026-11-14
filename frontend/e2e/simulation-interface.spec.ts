import { expect, test } from "@playwright/test";

test.afterEach(async ({ page }) => {
  await page.evaluate(async () => {
    const response = await fetch("/api/simulacao/status");
    if (!response.ok) return;
    const status: { estado_fsm: string } = await response.json();
    if (status.estado_fsm === "PAUSADO") {
      await fetch("/api/simulacao/resume", { method: "POST" });
    }
  });
  await page.waitForFunction(
    async () => (await fetch("/api/simulacao/status")).status === 404,
    undefined,
    { timeout: 10_000 },
  );
});

test("desktop simulation interface is served through the Compose network", async ({ page }) => {
  const response = await page.goto("/");

  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "ArchPath" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Caractere de entrada" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Iniciar simulação" })).toBeDisabled();
  await expect(page.getByRole("heading", { name: "Jornada do dado" })).toBeVisible();
});

test("simulation controls fit a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "ArchPath" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Caractere de entrada" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Iniciar simulação" })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
});

test("normal journey completes through the browser and returns the API to idle", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Caractere de entrada" }).fill("A");
  await expect(page.getByRole("slider", { name: "Velocidade visual" })).toBeDisabled();
  await expect(page.locator(".speed-control output")).toHaveText("1000 ms");
  await expect(page.getByRole("button", { name: "Iniciar simulação" })).toBeEnabled();
  await page.getByRole("button", { name: "Iniciar simulação" }).click();

  const eventRows = page.getByRole("region", { name: "Eventos recebidos" }).locator("li");
  await expect(eventRows).toHaveCount(21, { timeout: 30_000 });
  await expect(page.getByText("Resultado: sucesso")).toBeVisible();
  await expect(page.locator(".status-pill")).toHaveText("FINALIZADO");

  const sequences = await page.locator(".event-sequence").allTextContents();
  expect(sequences).toEqual(Array.from({ length: 21 }, (_, index) => `#${21 - index}`));

  for (const phase of [
    "Nascimento do dado",
    "I/O",
    "CPU",
    "Sistema Operacional",
    "Memória",
    "DMA",
    "Rede",
    "Saída Física",
  ]) {
    await expect(page.getByRole("heading", { name: phase, exact: true })).toBeVisible();
  }
  await expect(page.locator(".phase-complete")).toHaveCount(7);
  await expect(page.locator(".phase-current")).toHaveCount(1);

  await expect
    .poll(async () =>
      page.evaluate(async () => (await fetch("/api/simulacao/status")).status),
    )
    .toBe(404);
});

test("Page Fault is terminal and a new browser session can start afterward", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/");
  await page.getByRole("textbox", { name: "Caractere de entrada" }).fill("B");
  await page.getByRole("combobox", { name: "Cenário de memória" }).selectOption("page_fault");
  await expect(page.getByRole("button", { name: "Iniciar simulação" })).toBeEnabled();
  await page.getByRole("button", { name: "Iniciar simulação" }).click();

  const eventRows = page.getByRole("region", { name: "Eventos recebidos" }).locator("li");
  await expect(eventRows).toHaveCount(11, { timeout: 20_000 });
  await expect(page.getByText("Resultado: erro")).toBeVisible();
  await expect(page.locator(".status-pill")).toHaveText("FINALIZADO");

  const pageFaultEvents = await eventRows.allTextContents();
  expect(pageFaultEvents.join(" ")).toContain("GerenciadorMemoria");
  expect(pageFaultEvents.join(" ")).not.toContain("BufferTemporario");
  expect(pageFaultEvents.join(" ")).not.toContain("ControladorDMA");
  expect(pageFaultEvents.join(" ")).not.toContain("ControladorPHY");

  const previousSession = await page.locator(".session-id code").textContent();
  await page.getByRole("textbox", { name: "Caractere de entrada" }).fill("C");
  await page.getByRole("combobox", { name: "Cenário de memória" }).selectOption("normal");
  await page.getByRole("button", { name: "Iniciar simulação" }).click();

  await expect(eventRows).toHaveCount(21, { timeout: 30_000 });
  await expect(page.getByText("Resultado: sucesso")).toBeVisible();
  const nextSession = await page.locator(".session-id code").textContent();
  expect(nextSession).not.toBe(previousSession);
});

test("browser can step once and resume a paused real API session", async ({ page }) => {
  await page.goto("/");
  await expect
    .poll(() =>
      page.evaluate(async () => (await fetch("/api/simulacao/status")).status),
    )
    .toBe(404);
  await expect(page.locator(".status-pill")).toHaveText("OCIOSO");
  await page.getByRole("textbox", { name: "Caractere de entrada" }).fill("D");
  await expect(page.getByRole("slider", { name: "Velocidade visual" })).toBeDisabled();
  await expect(page.locator(".speed-control output")).toHaveText("1000 ms");
  await expect(page.getByRole("button", { name: "Iniciar simulação" })).toBeEnabled();

  const startResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/simulacao/iniciar"),
  );
  await page.getByRole("button", { name: "Iniciar simulação" }).click();
  expect((await startResponse).status()).toBe(200);
  await expect
    .poll(() =>
      page.evaluate(async () => {
        const response = await fetch("/api/simulacao/status");
        if (response.status !== 200) return null;
        const body = await response.json();
        return body.estado_fsm === "RODANDO" ? body.sessao_id : null;
      }),
    )
    .not.toBeNull();

  const eventRows = page.getByRole("region", { name: "Eventos recebidos" }).locator("li");
  await expect(eventRows).toHaveCount(1, { timeout: 5_000 });
  const snapshotBeforePause = await page.locator(".component-name").textContent();
  const visibleEventsBeforePause = await eventRows.count();
  await page.route("**/api/simulacao/pause", async (route) => {
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 1_500));
    await route.fulfill({ response });
  });

  const pauseResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/simulacao/pause"),
  );
  await page.getByRole("button", { name: "Pausar" }).click();
  await expect(page.getByText("Pausando…")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(async () => {
        const response = await fetch("/api/simulacao/status");
        return response.status === 200 ? (await response.json()).estado_fsm : "OCIOSO";
      }),
    )
    .toBe("PAUSADO");
  await page.waitForTimeout(1_100);
  await expect(page.locator(".component-name")).toHaveText(snapshotBeforePause ?? "");
  await expect(eventRows).toHaveCount(visibleEventsBeforePause);

  const pausedResponse = await pauseResponse;
  expect(pausedResponse.status()).toBe(200);
  const pauseConfirmation = await pausedResponse.json();
  expect(pauseConfirmation.evento.status_fsm).toBe("PAUSADO");
  expect(pauseConfirmation.evento.sessao_id).toBe(pauseConfirmation.sessao_id);
  expect(pauseConfirmation.sequencia_evento).toBeGreaterThan(0);
  await expect(page.locator(".event-sequence").first()).toHaveText(
    `#${pauseConfirmation.sequencia_evento}`,
  );
  await expect(page.locator(".component-name")).toHaveText(
    pauseConfirmation.evento.componente_atual,
  );
  await page.unroute("**/api/simulacao/pause");
  await expect(page.locator(".simulation-notice-paused")).toHaveText("Simulação pausada.");
  await expect(page.getByRole("button", { name: "Retomar" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Avançar uma etapa" })).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByText("Não há simulação ativa.")).toHaveCount(0);

  const pausedStatus = await page.evaluate(async () => (await fetch("/api/simulacao/status")).json());
  const pausedSnapshotComponent = await page.locator(".component-name").textContent();
  const pausedEventCount = await eventRows.count();
  await page.waitForTimeout(200);
  const unchangedStatus = await page.evaluate(async () => (await fetch("/api/simulacao/status")).json());
  expect(unchangedStatus.componente_atual).toBe(pausedStatus.componente_atual);
  await expect(page.locator(".component-name")).toHaveText(pausedSnapshotComponent ?? "");
  await expect(eventRows).toHaveCount(pausedEventCount);

  const stepResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/simulacao/step"),
  );
  await page.getByRole("button", { name: "Avançar uma etapa" }).click();
  const steppedResponse = await stepResponse;
  expect(steppedResponse.status()).toBe(200);
  const stepConfirmation = await steppedResponse.json();
  const stepStatus = await page.evaluate(async () => (await fetch("/api/simulacao/status")).json());
  expect(stepStatus.estado_fsm).toBe("PAUSADO");
  expect(stepStatus.componente_atual).not.toBe(pausedStatus.componente_atual);
  expect(stepConfirmation.evento.status_fsm).toBe("PAUSADO");
  expect(stepConfirmation.sequencia_evento).toBeGreaterThan(pauseConfirmation.sequencia_evento);
  await expect(page.locator(".event-sequence").first()).toHaveText(
    `#${stepConfirmation.sequencia_evento}`,
  );
  await expect(page.locator(".component-name")).toHaveText(
    stepConfirmation.evento.componente_atual,
  );
  await expect(page.locator(".simulation-notice-paused")).toHaveText("Simulação pausada.");
  await expect(page.getByRole("button", { name: "Retomar" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Avançar uma etapa" })).toBeEnabled();

  const resumeResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/simulacao/resume"),
  );
  await page.getByRole("button", { name: "Retomar" }).click();
  expect((await resumeResponse).status()).toBe(200);
  await expect
    .poll(() =>
      page.evaluate(async () => {
        const response = await fetch("/api/simulacao/status");
        if (response.status !== 200) return null;
        const body = await response.json();
        return body.estado_fsm === "RODANDO" ? body.componente_atual : null;
      }),
    )
    .not.toBe(stepStatus.componente_atual);

  await expect(eventRows).toHaveCount(21, { timeout: 30_000 });
  await expect
    .poll(() =>
      page.evaluate(async () => (await fetch("/api/simulacao/status")).status),
    )
    .toBe(404);
  await expect(page.getByText("Resultado: sucesso")).toBeVisible();
});

test("stale visual events do not keep the simulation running after the backend finishes", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Caractere de entrada" }).fill("F");
  await expect(page.getByRole("slider", { name: "Velocidade visual" })).toBeDisabled();
  await expect(page.locator(".speed-control output")).toHaveText("1000 ms");
  await page.getByRole("button", { name: "Iniciar simulação" }).click();

  await expect
    .poll(() =>
      page.evaluate(async () => (await fetch("/api/simulacao/status")).status),
      { timeout: 10_000 },
    )
    .toBe(404);
  await expect(page.locator(".status-pill")).toHaveText("RODANDO");
  await expect(page.getByRole("button", { name: "Pausar" })).toBeEnabled();

  const pauseResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/simulacao/pause"),
  );
  await page.getByRole("button", { name: "Pausar" }).click();
  expect((await pauseResponse).status()).toBe(400);
  await expect
    .poll(() =>
      page.evaluate(async () => (await fetch("/api/simulacao/status")).status),
    )
    .toBe(404);
  await expect(page.locator(".status-pill")).toHaveText("OCIOSO");
  await expect(page.getByRole("button", { name: "Pausar" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Retomar" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Avançar uma etapa" })).toBeDisabled();

  await page.waitForTimeout(1_100);
  await expect(page.locator(".status-pill")).toHaveText("OCIOSO");
  await expect(page.getByRole("alert")).toHaveText("A simulação já foi concluída.");
});
