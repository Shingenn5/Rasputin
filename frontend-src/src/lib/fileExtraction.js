import { postJson } from "../api/client.js";

const CLIENT_MAX_BYTES = 12_000_000;

function fileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.slice(value.indexOf(",") + 1) : value);
    };
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.readAsDataURL(file);
  });
}

export async function uploadAttachment(file, retention = "use_once") {
  if (!file) throw new Error("Choose a file to attach.");
  if (file.size > CLIENT_MAX_BYTES) {
    throw new Error(`${file.name} exceeds the 12 MB attachment limit.`);
  }
  const contentBase64 = await fileAsBase64(file);
  return postJson("/api/intake", {
    name: file.name,
    mimeType: file.type || "application/octet-stream",
    sizeBytes: file.size,
    contentBase64,
    retention,
  });
}

export function updateAttachmentRetention(intakeId, retention) {
  return postJson(`/api/intake/${encodeURIComponent(intakeId)}/retention`, { retention });
}

export function deleteAttachment(intakeId) {
  return postJson(`/api/intake/${encodeURIComponent(intakeId)}/delete`, {});
}

export function readableAttachmentSize(bytes) {
  const value = Number(bytes || 0);
  if (value < 1000) return `${value} B`;
  if (value < 1_000_000) return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)} KB`;
  return `${(value / 1_000_000).toFixed(1)} MB`;
}
