import { defineConfig, devices } from "@playwright/test";

// Testes de navegador (secao 17). Requer a aplicacao servida em BASE_URL e, para
// fluxos completos, o Firebase Emulator Suite ativo.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:8080",
    trace: "on-first-retry",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
