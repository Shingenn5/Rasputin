import asyncio
import json
import urllib.request

from . import model_registry


def LOCAL_MODELS():
    return {m["key"]: {"url": m.get("url", ""), "model": m.get("model", "")} for m in model_registry.all_models()}


async def chat(model_key, messages, temperature=0.2):
    cfg = model_registry.get_model(model_key) or model_registry.get_model("dry-run")
    url = model_registry.chat_url(cfg)
    if model_key == "dry-run" or cfg.get("provider") == "mock" or not url:
        user_msg = messages[-1]["content"] if messages else ""
        return f"[dry-run] I would process: {user_msg[:500]}"
    from . import security
    security.require_local_url(url)

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    def post_it():
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
        return json.loads(raw)

    data = await asyncio.to_thread(post_it)
    return data["choices"][0]["message"]["content"]
