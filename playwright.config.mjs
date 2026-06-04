import { defineConfig, devices } from "@playwright/test";

const baseUrl = process.env.RASPUTIN_TEST_BASE_URL || "http://127.0.0.1:8877";

export default defineConfig({
  testDir: "./tests/ui",
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
