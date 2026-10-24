import asyncio
import base64

import httpx

gemini_base = "https://generativelanguage.googleapis.com/v1beta"
gemini_url = gemini_base + "/models/{model}:generateContent"

# keep connections open between taps, a fresh secure connection costs most of a second
keep_alive = httpx.Limits(max_keepalive_connections=5, keepalive_expiry=300)

# server side errors worth one more try
retry_codes = {500, 502, 503, 504}

# a normal answer takes about two seconds, past this a backup request is sent
hedge_after = 3.5


class model_error(Exception):
    pass


class gemini_client:
    # gemma 4 through the gemini api, the default backend

    def __init__(self, api_key, model, timeout=40.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.use_thinking_config = True
        self.name = f"gemini api, {model}"
        self.http = None

    def client(self):
        # made on first use so it belongs to the running event loop
        if self.http is None or self.http.is_closed:
            self.http = httpx.AsyncClient(timeout=self.timeout, limits=keep_alive)
        return self.http

    def build_body(self, prompt, image_bytes, max_tokens=512):
        body = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}},
                    {"text": prompt},
                ],
            }],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens},
        }
        if self.use_thinking_config:
            # thinking off keeps answers fast, speed matters more than depth here
            body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "minimal"}
        return body

    async def warm_up(self):
        # open the connection before the first tap so it is not slower than the rest
        if self.api_key:
            await self.client().get(f"{gemini_base}/models/{self.model}", headers={"x-goog-api-key": self.api_key})

    async def ask(self, prompt, image_bytes, max_tokens=512):
        if not self.api_key:
            raise model_error("GEMINI_API_KEY is not set")
        first = asyncio.create_task(self.ask_once(prompt, image_bytes, max_tokens))
        done, _ = await asyncio.wait({first}, timeout=hedge_after)
        if done:
            return first.result()
        # google is having a slow moment, send a backup and take whichever answers first
        backup = asyncio.create_task(self.ask_once(prompt, image_bytes, max_tokens))
        waiting = {first, backup}
        error = None
        while waiting:
            done, waiting = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task.exception() is None:
                    for other in waiting:
                        other.cancel()
                    return task.result()
                error = task.exception()
        raise error

    async def ask_once(self, prompt, image_bytes, max_tokens):
        url = gemini_url.format(model=self.model)
        headers = {"x-goog-api-key": self.api_key, "content-type": "application/json"}
        client = self.client()
        response = await client.post(url, headers=headers, json=self.build_body(prompt, image_bytes, max_tokens))
        if response.status_code == 400 and self.use_thinking_config and "thinking" in response.text.lower():
            # older model versions reject the thinking setting, so drop it and retry once
            self.use_thinking_config = False
            response = await client.post(url, headers=headers, json=self.build_body(prompt, image_bytes, max_tokens))
        if response.status_code in retry_codes:
            # google sometimes has a one off hiccup, one quick retry usually works
            await asyncio.sleep(0.3)
            response = await client.post(url, headers=headers, json=self.build_body(prompt, image_bytes, max_tokens))
        if response.status_code != 200:
            raise model_error(f"gemini api returned {response.status_code}: {response.text[:300]}")
        return read_gemini_text(response.json())

    async def close(self):
        if self.http is not None:
            await self.http.aclose()


def read_gemini_text(data):
    candidates = data.get("candidates") or []
    if not candidates:
        raise model_error(f"no answer from the model: {str(data)[:300]}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    # skip thought parts, only the final answer is spoken
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


class ollama_client:
    # optional offline backend, runs an open weight gemma model on the same machine

    def __init__(self, host, model, timeout=120.0):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.name = f"ollama, {model}"
        self.http = None

    def client(self):
        if self.http is None or self.http.is_closed:
            self.http = httpx.AsyncClient(timeout=self.timeout, limits=keep_alive)
        return self.http

    async def warm_up(self):
        pass

    async def ask(self, prompt, image_bytes, max_tokens=512):
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(image_bytes).decode()]}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": max_tokens},
        }
        try:
            response = await self.client().post(f"{self.host}/api/chat", json=body)
        except httpx.HTTPError as err:
            raise model_error(f"could not reach ollama at {self.host}: {err}") from err
        if response.status_code != 200:
            raise model_error(f"ollama returned {response.status_code}: {response.text[:300]}")
        return (response.json().get("message") or {}).get("content", "")

    async def close(self):
        if self.http is not None:
            await self.http.aclose()
