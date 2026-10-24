GemmaSight

An open source visual co-pilot for blind and low vision people, powered by Gemma 4.

Point your phone forward, tap a big button, and GemmaSight tells you out loud what the camera sees. It reads labels and money, describes what is ahead with hazards first, and guides you to a lost object with clock directions and beeps that come from the side the object is on.

Why

Most help for blind users today means asking another person, or using apps that only work in English. GemmaSight runs in any phone browser, needs no install, speaks English and Kiswahili, and is built on an open weight model so anyone can study it, improve it or run it themselves.

What it does

- Read - reads what is in front of the camera and says first what matters most for that kind of item. It knows 18 kinds of everyday things, listed in `app/everyday_items.py`. Some examples: the dose and expiry date on medicine, Kenyan shilling notes and coins, expiry dates and allergens on food, the amount, balance and code in mobile money messages, appliance dials, electricity tokens, clothing labels, matatu route numbers, receipts and bills. It never guesses missing text, and if a PIN or card number is visible it says it is there without reading it aloud. To add a new kind of item, add one line to that file.

- Describe - up to two short sentences about what is in front of you. Anything in your path that could trip or hurt you is said first, with a warning tone and vibration.

- Distance in steps - Find, Describe and Ask give rough distances in walking steps, where one step is about 70 cm, like "about 3 steps away", or "within reach" for things at arm's length. They are always said as about, because they are estimates from a single photo.

- Find - say what you are looking for, like "my keys". GemmaSight keeps checking the camera and says where it is. The Directions button picks how. Clock gives positions like "keys, at 11 o'clock, about 2 steps away", the way many blind people are taught. Left, right gives plain words like "keys, slightly to your left, about 2 steps away". The choice is remembered. The beeps are panned left or right toward the object and get higher as it gets closer. It stops by itself when the object is right in front of you.

- Ask - speak any question about what the camera sees.

- Listening - Find and Ask start listening the moment you tap, with a rising tone and a short buzz. They listen for up to 30 seconds, with a countdown on screen and a soft beep when 5 seconds are left. Listening ends sooner once you stop talking for a moment, or straight away if you tap the button again. Camera and microphone permission are both asked for when the app starts.

- Noise handling - speech is turned into text by the phone's own speech engine, which does its own noise filtering. On top of that GemmaSight takes the most confident of several guesses, ignores very unsure results that are usually background noise, drops filler sounds such as um and eh, and only counts new words toward the end of listening so steady noise does not keep the mic open. It tries Kenyan English first and falls back to US English where that is not installed. If the microphone is blocked, a text box appears instead.

- Kiswahili - one tap switches speech in, speech out and the answers to Kiswahili. In Kiswahili, directions start as left and right words, because Swahili time telling uses a different clock. Clock positions are still there on the Directions button and say "kwenye uso wa saa", on the clock face, so they are not mistaken for the time of day.

How it works

- The web app in `static/` opens the rear camera, listens with the browser's speech recognition and talks back with the browser's built in voice. No audio leaves the phone for speech.

- When you tap a button, one frame is shrunk to 768 pixels and sent with the task to the small Python server in `app/`.

- The server asks Gemma 4 through the Gemini API to look at the image and reply with a small JSON object.

- For Find, Gemma only says roughly where the object is, from left to right, and how near it is. The server turns that into the same clock or left, right phrase every time, so directions are always said the same way and never made up.

- Thinking is turned off on the model call to keep answers fast.

How Gemma 4 is used

- Model - `gemma-4-26b-a4b-it` by default, set with `GEMMASIGHT_MODEL`. `gemma-4-31b-it` also works and is slower.

- Multimodal input - every request sends the camera image together with the text task in one call.

- Structured output - each mode asks for a fixed JSON shape, and `app/guidance.py` checks it and fills in safe defaults if a field is missing or odd.

- Open weights - setting `GEMMASIGHT_BACKEND=ollama` sends the same prompts to a Gemma model running locally in Ollama instead. This path is experimental and has not been tested on a phone demo yet.

Run it locally

You need Python 3.10 or newer and a Gemini API key from https://aistudio.google.com/apikey.

    git clone https://github.com/808kirai/GemmaSight.git
    cd GemmaSight
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env

On macOS or Linux use `source .venv/bin/activate` and `cp .env.example .env`.

Put your key in `.env` after `GEMINI_API_KEY=`, then start the server.

    uvicorn app.main:app --port 8000

Open http://localhost:8000 in Chrome on the same computer and tap anywhere to start.

Use it on a phone

Phone browsers only allow the camera on https pages. Two easy ways to get one.

- Cloudflare tunnel - install `cloudflared`, run `cloudflared tunnel --url http://localhost:8000` and open the https link it prints on your phone.

- DigitalOcean App Platform - create an app from this GitHub repo, it builds from the `Dockerfile`. Add `GEMINI_API_KEY` as an encrypted environment variable. App Platform gives you an https link.

GemmaSight picks a female voice when the device has one. It prefers the Kenyan voices Asilia for English and Zuri for Kiswahili where they are installed. Which voices exist depends on the phone and browser.

Speech recognition works best in Chrome on Android. On iPhone, Safari can read answers aloud. If speech recognition is missing, a text box appears instead.

Settings

- `GEMINI_API_KEY` - Your Gemini API key, required for the default backend

- `GEMMASIGHT_MODEL` - Gemma model name, defaults to `gemma-4-26b-a4b-it`

- `GEMMASIGHT_BACKEND` - `gemini` or `ollama`, defaults to `gemini`

- `OLLAMA_HOST` - Ollama address, defaults to `http://localhost:11434`

- `GEMMASIGHT_OLLAMA_MODEL` - Model name in Ollama, defaults to `gemma4`. Check `ollama list` for the exact name on your machine

Keyboard shortcuts

- `1` - Read

- `2` - Describe

- `3` - Find

- `4` - Ask

- `r` - Repeat the last answer

- `d` - Switch directions between clock and left, right

- `l` - Switch language

- `Esc` - Stop listening, or stop Find

Project layout

- `app/main.py` - Web server, the `/api/ask` endpoint and image checks

- `app/prompts.py` - The instructions sent to Gemma for each mode

- `app/everyday_items.py` - The kinds of everyday items Read knows, and what to say first for each

- `app/guidance.py` - Reads the model reply and builds what gets spoken

- `app/model.py` - Gemini API and Ollama clients

- `static/` - The phone web app

- `tests/` - Tests, run with `pytest`

Safety

GemmaSight is an aid, not a replacement for a white cane, guide dog or a trusted person. The model can miss things or be wrong, and each answer takes a few seconds, which is too slow for moving traffic. Always check medicine with a pharmacist or someone you trust before taking it.

Privacy

Camera frames are sent to the Gemini API only when you tap a button or while Find is running. Nothing is stored on the server. With the Ollama backend, images stay on your own machine. The Inter font is loaded from Google Fonts, and the app falls back to the system font when offline.

Contributing

Issues and pull requests are welcome, especially more languages, better prompts and testing with blind and low vision users.

License

MIT, see `LICENSE`. Gemma models are provided under Google's Gemma terms.
