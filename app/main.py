import base64
import binascii
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.guidance import build_answer
from app.model import gemini_client, model_error, ollama_client
from app.prompts import build_prompt

load_dotenv()

project_root = Path(__file__).resolve().parent.parent
static_dir = project_root / "static"
max_image_bytes = 4 * 1024 * 1024
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gemmasight")

model_down_words = {
    "en": "I could not reach the model. Please try again.",
    "sw": "Sikuweza kufikia modeli. Tafadhali jaribu tena.",
}


def make_client():
    if os.getenv("GEMMASIGHT_BACKEND", "gemini").lower() == "ollama":
        return ollama_client(
            os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            os.getenv("GEMMASIGHT_OLLAMA_MODEL", "gemma4"),
        )
    return gemini_client(
        os.getenv("GEMINI_API_KEY", ""),
        os.getenv("GEMMASIGHT_MODEL", "gemma-4-26b-a4b-it"),
    )


@asynccontextmanager
async def lifespan(app):
    try:
        await app.state.model_client.warm_up()
    except Exception as err:
        # a failed warm up only means the first answer is a little slower
        log.warning("warm up failed: %s", err)
    yield
    await app.state.model_client.close()


app = FastAPI(title="GemmaSight", lifespan=lifespan)
app.state.model_client = make_client()

# a cap on answer length per mode, shorter limits come back sooner
max_tokens_by_mode = {"read": 240, "describe": 160, "find": 160, "ask": 160}


class ask_request(BaseModel):
    mode: Literal["read", "describe", "find", "ask"]
    image: str
    text: str = Field("", max_length=200)
    lang: Literal["en", "sw"] = "en"
    # how find mode says where things are, empty means the default for the language
    directions: Optional[Literal["clock", "words"]] = None


def decode_image(image):
    # the browser sends a data url, keep only the base64 part
    if image.startswith("data:"):
        image = image.split(",", 1)[-1]
    try:
        data = base64.b64decode(image, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "image is not valid base64")
    if len(data) > max_image_bytes:
        raise HTTPException(413, "image is too large")
    if not data.startswith(b"\xff\xd8"):
        raise HTTPException(400, "image must be a jpeg")
    return data


@app.get("/api/health")
async def health():
    return {"ok": True, "backend": app.state.model_client.name}


@app.post("/api/ask")
async def ask(request: ask_request):
    if request.mode in ("find", "ask") and not request.text.strip():
        raise HTTPException(400, "find and ask need some text")
    image_bytes = decode_image(request.image)
    prompt = build_prompt(request.mode, request.text, request.lang)
    started = time.perf_counter()
    try:
        raw = await app.state.model_client.ask(prompt, image_bytes, max_tokens_by_mode[request.mode])
        log.info("%s answered in %.1fs", request.mode, time.perf_counter() - started)
    except (model_error, httpx.HTTPError) as err:
        log.warning("model call failed: %s", err)
        return {"speech": model_down_words[request.lang], "hazard": False, "found": False,
                "position": None, "clock": None, "distance": None, "error": True}
    return build_answer(request.mode, raw, request.lang, request.directions)


# the web app itself, mounted last so the api routes win
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
