import { api, postJson } from "../api/client.js";

export function useIntegrationActions(context) {
  const {
    setSkillPreview,
    setGlobalStatus,
    setSkillRegistry,
    setTelegramConfig,
    telegramConfig,
    setSchedulesList,
  } = context;

  async function createSkillFromSession(sessionId) {
    if (!sessionId) return;
    setSkillPreview(await postJson("/api/skills/create-from-session", { sessionId, save: false }));
    setGlobalStatus("Skill preview created.");
  }

  async function enableSkill(name) {
    await postJson(`/api/skills/${name}/enable`, {});
    setSkillRegistry(await api("/api/skills"));
  }

  async function disableSkill(name) {
    await postJson(`/api/skills/${name}/disable`, {});
    setSkillRegistry(await api("/api/skills"));
  }

  async function configureTelegram(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setTelegramConfig(await postJson("/api/integrations/telegram/configure", {
      botToken: form.get("botToken") || undefined,
      allowedChatId: form.get("allowedChatId"),
      redactionMode: form.get("redactionMode") || "summary",
      enabled: form.get("enabled") === "on",
    }));
    setGlobalStatus("Telegram settings saved.");
  }

  async function testTelegram() {
    try {
      const result = await postJson("/api/integrations/telegram/test", {});
      setTelegramConfig(result.result || telegramConfig);
      setGlobalStatus(result.sent ? "Telegram test sent." : "Telegram test skipped.");
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function createSchedule(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await postJson("/api/schedules", {
      name: form.get("name"),
      prompt: form.get("prompt"),
      intervalSeconds: Number(form.get("intervalSeconds") || 0),
      enabled: form.get("enabled") === "on",
    });
    event.currentTarget.reset();
    setSchedulesList(await api("/api/schedules"));
    setGlobalStatus("Schedule saved.");
  }

  return { createSkillFromSession, enableSkill, disableSkill, configureTelegram, testTelegram, createSchedule };
}
