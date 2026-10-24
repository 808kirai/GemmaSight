import base64

import httpx

gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


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

    def build_body(self, prompt, image_bytes):
        body = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}},
                    {"text": prompt},
                ],
            }],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512},
        }
        if self.use_thinking_config:
            # thinking off keeps answers fast, speed matters more than depth here
            body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "minimal"}
        return body

    async def ask(self, prompt, image_bytes):
        if not self.api_key:
            raise model_error("GEMINI_API_KEY is not set")
        url = gemini_url.format(model=self.model)
        headers = {"x-goog-api-key": self.api_key, "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=self.build_body(prompt, image_bytes))
            if response.status_code == 400 and self.use_thinking_config and "thinking" in response.text.lower():
                # older model versions reject the thinking setting, so drop it and retry once
                self.use_thinking_config = False
                response = await client.post(url, headers=headers, json=self.build_body(prompt, image_bytes))
        if response.status_code != 200:
            raise model_error(f"gemini api returned {response.status_code}: {response.text[:300]}")
        return read_gemini_text(response.json())


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

    async def ask(self, prompt, image_bytes):
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(image_bytes).decode()]}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.host}/api/chat", json=body)
        except httpx.HTTPError as err:
            raise model_error(f"could not reach ollama at {self.host}: {err}") from err
        if response.status_code != 200:
            raise model_error(f"ollama returned {response.status_code}: {response.text[:300]}")
        return (response.json().get("message") or {}).get("content", "")
