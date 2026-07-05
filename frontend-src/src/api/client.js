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
export async function postJsonStream(path, data, onProgress) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Request failed: ${response.status} ${text}`);
  }
  // The server answers fast requests as plain JSON and long-running ones as
  // NDJSON — accept both so callers don't need to know in advance.
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("ndjson")) {
    const body = await response.json();
    if (body.ok === false) throw new Error(body.error?.message || body.error);
    return body?.ok === true && Object.prototype.hasOwnProperty.call(body, "data") ? body.data : body;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let result = null;
  let buffer = "";
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop(); // keep the last incomplete line in the buffer
    
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const payload = JSON.parse(line);
        if (payload.ok === false) throw new Error(payload.error?.message || payload.error);
        if (payload.final) {
          result = payload.data;
        } else {
          onProgress?.(payload.data);
        }
      } catch (e) {
        if (e instanceof SyntaxError) {
          // In case the line somehow wasn't fully parsed, ignore it. 
          // But our split by newline should guarantee complete lines for NDJSON.
        } else {
          throw e;
        }
      }
    }
  }
  return result;
}
