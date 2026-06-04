export async function api(path, options = {}) {
  const response = await fetch(path, options);
  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = { error: await response.text() };
  }
  if (!response.ok || payload.ok === false) {
    const error = payload?.error;
    throw new Error(error?.message || payload.message || payload.error || `Request failed: ${response.status}`);
  }
  return payload?.ok === true && Object.prototype.hasOwnProperty.call(payload, "data") ? payload.data : payload;
}

export function postJson(path, data) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}
