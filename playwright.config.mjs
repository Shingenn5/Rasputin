import { defineConfig, devices } from "@playwright/test";

const baseUrl = process.env.RASPUTIN_TEST_BASE_URL || "http://127.0.0.1:8877";

export default defineConfig({
  testDir: "./tests/ui",
  // The isolated harness uses one shared backend/data directory. Serializing
  // specs prevents one browser from changing preferences, sessions, or task
  // queue state while another spec is asserting it.
  workers: 1,
  timeout: 30000,
  expect: {
    timeout: 8000
  },
  use: {
    baseURL: baseUrl,
    trace: "on-first-retry",
    screenshot: "only-on-failure"
  },
  reporter: [["list"], ["html", { open: "never" }]],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
