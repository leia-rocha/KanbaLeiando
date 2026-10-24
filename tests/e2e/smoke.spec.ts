import { test, expect } from "@playwright/test";

// Smoke de disponibilidade e identidade visual (CA33, CA34). Nao exige login:
// valida que a SPA carrega, o tema escuro e o logo estao presentes e a API
// responde. Fluxos autenticados completos exigem emuladores e dados de teste.

test("healthz responde ok", async ({ request }) => {
  const res = await request.get("/api/v1/healthz");
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  expect(body.status).toBe("ok");
});

test("config nao expoe segredos", async ({ request }) => {
  const res = await request.get("/api/v1/config");
  expect(res.ok()).toBeTruthy();
  const cfg = await res.json();
  // So valores publicos (secao 15.3): nada de admin/smtp/segredos.
  expect(cfg).not.toHaveProperty("adminPassword");
  expect(cfg).not.toHaveProperty("smtpPassword");
  expect(cfg).not.toHaveProperty("publicLinkSecret");
  expect(cfg).toHaveProperty("firebaseApiKey");
});

test("tela de login carrega com logo e tema escuro", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("img", { name: "KanbaLeiando" })).toBeVisible();
  await expect(page.getByLabel("E-mail")).toBeVisible();
  await expect(page.getByLabel("Senha")).toBeVisible();
  const bg = await page.evaluate(() =>
    getComputedStyle(document.body).backgroundColor,
  );
  // Fundo escuro (#212121 => rgb(33, 33, 33)).
  expect(bg).toBe("rgb(33, 33, 33)");
});

test("rota de API inexistente retorna JSON e nao o index.html", async ({ request }) => {
  const res = await request.get("/api/v1/rota-que-nao-existe");
  expect(res.status()).toBe(404);
  const body = await res.json();
  expect(body.error).toBeTruthy();
});
