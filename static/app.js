// gemmasight front end, built so it can be used without looking at the screen

const words = {
  en: {
    ready: "GemmaSight is ready. The buttons are Read, Describe, Find and Ask. For Find and Ask, speak after the rising tone.",
    looking: "Looking.",
    what_find: "Listening. Say what to find.",
    ask_question: "Listening. Ask your question.",
    mic_blocked: "The microphone is blocked, so please type instead. You can allow it in your browser settings.",
    no_speech: "I did not hear anything. Please try again.",
    searching: "Looking for",
    stopped: "Stopped looking.",
    in_reach: "It should be right in front of you.",
    no_camera: "I cannot open the camera. Please allow camera access and reload.",
    down: "I could not reach the server. Please check the connection.",
    lang_name: "English",
    lang_label: "Language, English. Tap for Kiswahili",
    type_find: "Type what to find",
    type_ask: "Type your question",
    clock_button: "Clock",
    words_button: "Left, right",
    clock_label: "Directions, clock. Tap for left and right",
    words_label: "Directions, left and right. Tap for clock",
    clock_said: "Directions will use clock positions, like 11 o'clock.",
    words_said: "Directions will use left and right, like slightly to your left.",
  },
  sw: {
    ready: "GemmaSight iko tayari. Vitufe ni Soma, Eleza, Tafuta na Uliza. Kwa Tafuta na Uliza, ongea baada ya mlio unaopanda.",
    looking: "Ninaangalia.",
    what_find: "Ninasikiliza. Sema kitu cha kutafuta.",
    ask_question: "Ninasikiliza. Uliza swali lako.",
    mic_blocked: "Maikrofoni imezuiwa, tafadhali andika badala yake. Unaweza kuiruhusu kwenye mipangilio ya kivinjari.",
    no_speech: "Sikusikia chochote. Tafadhali jaribu tena.",
    searching: "Ninatafuta",
    stopped: "Nimeacha kutafuta.",
    in_reach: "Kiko mbele yako, karibu sana.",
    no_camera: "Siwezi kufungua kamera. Tafadhali ruhusu kamera kisha upakie upya.",
    down: "Sikuweza kufikia seva. Tafadhali angalia mtandao.",
    lang_name: "Kiswahili",
    lang_label: "Lugha, Kiswahili. Gusa kwa Kiingereza",
    type_find: "Andika kitu cha kutafuta",
    type_ask: "Andika swali lako",
    clock_button: "Saa",
    words_button: "Kushoto, kulia",
    clock_label: "Maelekezo, uso wa saa. Gusa kwa kushoto na kulia",
    words_label: "Maelekezo, kushoto na kulia. Gusa kwa uso wa saa",
    clock_said: "Maelekezo yatatumia uso wa saa, kama saa 11 kwenye uso wa saa.",
    words_said: "Maelekezo yatatumia kushoto na kulia, kama kushoto kidogo.",
  },
};

// clock suits english speakers trained in it, swahili time telling uses a different clock
const default_directions = { en: "clock", sw: "words" };

const speech_lang = { en: "en-US", sw: "sw-KE" };
const pan_by_position = { "left": -1, "slightly left": -0.5, "center": 0, "slightly right": 0.5, "right": 1 };
const pitch_by_distance = { near: 990, mid: 740, far: 520 };
const max_side = 768;
// find and ask listen for up to 30 seconds, and stop sooner once the user goes quiet
const listen_limit_ms = 30000;
const silence_ms = 2500;
// kenyan english first for local accents, with a fallback where it is not installed
const recognition_langs = { en: ["en-KE", "en-US"], sw: ["sw-KE", "sw-TZ"] };
const min_confidence = 0.35;
const filler_words = new Set(["uh", "um", "umm", "hmm", "mm", "mhm", "eh", "ah", "er", "erm", "oh"]);

const video = document.getElementById("camera");
const status_line = document.getElementById("status");
const busy_ring = document.getElementById("busy");
const lang_button = document.getElementById("lang");
const directions_button = document.getElementById("directions");
const timer_badge = document.getElementById("timer");

let lang = "en";
// null until the user picks, then their choice wins over the language default
let chosen_directions = null;
let busy = false;
let finding = false;
let find_target = "";
let last_speech = "";
let audio = null;
let wake_lock = null;

try {
  lang = localStorage.getItem("gemmasight-lang") === "sw" ? "sw" : "en";
  const saved = localStorage.getItem("gemmasight-directions");
  if (saved === "clock" || saved === "words") chosen_directions = saved;
} catch (err) {
  // storage can be blocked in private mode, english is fine then
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// speech out

// browsers do not say which voices are female, so match known female voice names
// best first, kenyan voices lead each list
const female_voices = {
  en: ["asilia", "jenny", "aria", "zira", "sonia", "libby", "hazel", "susan", "samantha", "karen", "moira", "tessa", "fiona", "serena", "victoria", "google us english", "google uk english female", "female"],
  sw: ["zuri", "rehema", "female"],
};
const male_voices = ["male", "david", "mark", "guy", "daniel", "alex", "fred", "george", "ryan", "rishi", "james", "daudi", "rafiki", "christopher", "eric"];

function pick_voice() {
  const voices = window.speechSynthesis ? speechSynthesis.getVoices() : [];
  const prefix = lang === "sw" ? "sw" : "en";
  const in_lang = voices.filter((v) => v.lang.toLowerCase().startsWith(prefix));
  const name_of = (v) => v.name.toLowerCase();
  for (const wanted of female_voices[lang]) {
    // "female" also appears inside "male", so match whole words for the generic ones
    const match = in_lang.find((v) => wanted === "female" ? /\bfemale\b/.test(name_of(v)) : name_of(v).includes(wanted));
    if (match) return match;
  }
  // no known female voice, at least avoid the known male ones
  const not_male = in_lang.find((v) => !male_voices.some((m) => new RegExp(`\\b${m}\\b`).test(name_of(v))));
  return not_male || in_lang[0] || null;
}

function speak(text) {
  return new Promise((resolve) => {
    if (!window.speechSynthesis || !text) return resolve();
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = speech_lang[lang];
    const voice = pick_voice();
    if (voice) utterance.voice = voice;
    utterance.rate = 1.05;
    // some browsers never fire onend, so a timer makes sure we move on
    const fallback = setTimeout(resolve, 1500 + text.length * 90);
    utterance.onend = utterance.onerror = () => {
      clearTimeout(fallback);
      resolve();
    };
    speechSynthesis.speak(utterance);
  });
}

// speech in

// set while the mic is open, calling it ends listening early and keeps what was heard
let stop_listening = null;

function show_timer(seconds) {
  timer_badge.hidden = seconds === null;
  if (seconds !== null) timer_badge.textContent = `0:${String(seconds).padStart(2, "0")}`;
}

function clean_heard(text) {
  // drop filler sounds, background noise often comes through as these
  return text
    .split(/\s+/)
    .filter((w) => w && !filler_words.has(w.toLowerCase().replace(/[^\p{L}]/gu, "")))
    .join(" ")
    .trim();
}

function rising_tone() {
  beep(660, 0.07, 0, 0.18);
  setTimeout(() => beep(990, 0.09, 0, 0.18), 90);
}

function listen(typed_hint) {
  const recognition_class = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!recognition_class) {
    // no speech recognition in this browser, typing still works for helpers and judges
    return Promise.resolve((window.prompt(typed_hint) || "").trim());
  }
  return new Promise((resolve) => {
    const deadline = Date.now() + listen_limit_ms;
    const langs = recognition_langs[lang];
    let lang_index = 0;
    let retry_lang = false;
    let final_text = "";
    let interim_text = "";
    let last_heard = "";
    let done = false;
    let blocked = false;
    let warned = false;
    let recognition = null;
    let silence_timer = null;

    const heard = () => clean_heard(`${final_text} ${interim_text}`);

    const tick = setInterval(() => {
      const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      show_timer(left);
      // one soft warning so the user knows time is nearly up
      if (left <= 5 && !warned) {
        warned = true;
        beep(660, 0.06, 0, 0.12);
      }
    }, 250);
    const hard_stop = setTimeout(finish, listen_limit_ms);
    show_timer(listen_limit_ms / 1000);

    function finish() {
      if (done) return;
      done = true;
      stop_listening = null;
      clearInterval(tick);
      clearTimeout(hard_stop);
      clearTimeout(silence_timer);
      show_timer(null);
      try {
        recognition.abort();
      } catch (err) {
        // already stopped
      }
      beep(520, 0.08, 0, 0.15);
      const result = heard();
      if (!result && blocked) {
        // mic or speech service refused, typing keeps find and ask usable
        show(words[lang].mic_blocked, "hazard");
        resolve((window.prompt(typed_hint) || "").trim());
      } else {
        resolve(result);
      }
    }

    function start_once() {
      recognition = new recognition_class();
      recognition.lang = langs[lang_index];
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 3;
      recognition.onresult = (event) => {
        interim_text = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          // take the most confident guess of the alternatives
          let best = result[0];
          for (let a = 1; a < result.length; a++) {
            if (result[a].confidence > best.confidence) best = result[a];
          }
          if (result.isFinal) {
            // very unsure final results are usually background noise, some browsers report 0 when they do not know
            if (best.confidence === 0 || best.confidence >= min_confidence) final_text += " " + best.transcript;
          } else {
            interim_text += " " + best.transcript;
          }
        }
        final_text = final_text.trim();
        const now_heard = heard();
        // only real new words count, so steady noise does not keep the mic open
        if (now_heard && now_heard !== last_heard) {
          last_heard = now_heard;
          show(`"${now_heard}"`);
          clearTimeout(silence_timer);
          silence_timer = setTimeout(finish, silence_ms);
        }
      };
      recognition.onerror = (event) => {
        if (event.error === "not-allowed" || event.error === "service-not-allowed") blocked = true;
        // the kenyan model is not on every phone, fall back to the next language code
        if (event.error === "language-not-supported" && lang_index < langs.length - 1) {
          lang_index += 1;
          retry_lang = true;
        }
      };
      recognition.onend = () => {
        if (done) return;
        if (retry_lang) {
          retry_lang = false;
          start_once();
          return;
        }
        // some phones close the mic after a short silence, reopen it until time runs out
        if (!heard() && !blocked && Date.now() < deadline - 500) start_once();
        else finish();
      };
      try {
        recognition.start();
      } catch (err) {
        blocked = true;
        finish();
      }
    }

    stop_listening = finish;
    // stop any speech first so the app does not hear itself
    if (window.speechSynthesis) speechSynthesis.cancel();
    // start inside the tap, iphones refuse to open the mic later
    start_once();
    rising_tone();
    if (navigator.vibrate) navigator.vibrate(60);
  });
}

// sound cues

function beep(freq, seconds, pan = 0, volume = 0.25) {
  if (!audio) return;
  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.frequency.value = freq;
  osc.type = "sine";
  gain.gain.setValueAtTime(volume, audio.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + seconds);
  let node = osc.connect(gain);
  if (audio.createStereoPanner) {
    // pan the beep toward the object so the ears point the way
    const panner = audio.createStereoPanner();
    panner.pan.value = pan;
    node = node.connect(panner);
  }
  node.connect(audio.destination);
  osc.start();
  osc.stop(audio.currentTime + seconds);
}

async function cue_found(answer) {
  const pan = pan_by_position[answer.position] ?? 0;
  const pitch = pitch_by_distance[answer.distance] ?? 740;
  for (let i = 0; i < 3; i++) {
    beep(pitch, 0.12, pan, 0.35);
    await wait(160);
  }
}

async function cue_hazard() {
  if (navigator.vibrate) navigator.vibrate([250, 100, 250]);
  beep(1320, 0.15, 0, 0.4);
  await wait(200);
  beep(1320, 0.15, 0, 0.4);
  await wait(250);
}

let tick_timer = null;

function set_busy(on) {
  busy = on;
  busy_ring.hidden = !on;
  clearInterval(tick_timer);
  // a soft tick while waiting so the user knows it is still working
  if (on) tick_timer = setInterval(() => beep(330, 0.04, 0, 0.12), 900);
}

// camera

async function start_camera() {
  const video_wanted = { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } };
  let stream;
  try {
    // ask for camera and mic together at the start so the permission prompt shows up front
    stream = await navigator.mediaDevices.getUserMedia({
      video: video_wanted,
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (err) {
    // mic refused, carry on with the camera alone and offer typing later
    stream = await navigator.mediaDevices.getUserMedia({ video: video_wanted, audio: false });
  }
  // release the mic straight away, speech recognition opens its own when needed
  // and an open mic on iphone sends the voice to the quiet earpiece
  stream.getAudioTracks().forEach((track) => track.stop());
  video.srcObject = new MediaStream(stream.getVideoTracks());
  await video.play();
}

function capture() {
  if (!video.videoWidth) throw new Error("camera not ready");
  // shrink the frame, smaller images come back faster and still read fine
  const scale = Math.min(1, max_side / Math.max(video.videoWidth, video.videoHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.75);
}

// talking to the server

async function ask_model(mode, text = "") {
  set_busy(true);
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ mode, text, lang, directions: current_directions(), image: capture() }),
    });
    if (!response.ok) throw new Error(`server returned ${response.status}`);
    return await response.json();
  } catch (err) {
    console.warn(err);
    return { speech: words[lang].down, hazard: false, found: false, error: true };
  } finally {
    set_busy(false);
  }
}

function show(text, kind = "") {
  status_line.textContent = text;
  status_line.className = "status" + (kind ? " " + kind : "");
  // start each new answer from the top of the box
  status_line.scrollTop = 0;
}

async function present(answer) {
  show(answer.speech, answer.hazard ? "hazard" : answer.found ? "found" : "");
  last_speech = answer.speech;
  if (answer.hazard) await cue_hazard();
  await speak(answer.speech);
}

// modes

function mark_active(mode) {
  document.querySelectorAll(".mode").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
}

async function run_mode(mode) {
  // a tap while the mic is open means they are done talking
  if (stop_listening) {
    stop_listening();
    return;
  }
  if (finding) {
    stop_find();
    if (mode === "find") return;
  }
  if (busy) return;
  mark_active(mode);
  try {
    if (mode === "read" || mode === "describe") {
      show(words[lang].looking);
      speak(words[lang].looking);
      await present(await ask_model(mode));
    } else if (mode === "ask") {
      const question = await prompt_for(words[lang].ask_question, words[lang].type_ask);
      if (question) {
        show(`"${question}"`);
        await present(await ask_model("ask", question));
      }
    } else if (mode === "find") {
      const heard = await prompt_for(words[lang].what_find, words[lang].type_find);
      // people often say find my keys, keep just the thing to look for
      const target = heard.replace(/^(please\s+)?(find|look for|search for|where is|where are|where's|tafuta|nitafutie)\s+/i, "").trim();
      if (target) await start_find(target);
    }
  } finally {
    if (!finding) mark_active(null);
  }
}

async function prompt_for(question, typed_hint) {
  // listen right away with a rising tone instead of a spoken prompt
  // phones only allow the mic during the tap, and the app would hear its own voice
  const listening = listen(typed_hint);
  show(question);
  const heard = await listening;
  if (!heard) {
    show(words[lang].no_speech);
    await speak(words[lang].no_speech);
  }
  return heard;
}

async function start_find(target) {
  finding = true;
  find_target = target;
  mark_active("find");
  await keep_screen_on(true);
  const intro = `${words[lang].searching} ${target}.`;
  show(intro);
  await speak(intro);

  let misses = 0;
  while (finding) {
    const answer = await ask_model("find", find_target);
    if (!finding) break;
    if (answer.found) {
      misses = 0;
      show(answer.speech, answer.hazard ? "hazard" : "found");
      last_speech = answer.speech;
      if (answer.hazard) await cue_hazard();
      await cue_found(answer);
      await speak(answer.speech);
      if (answer.position === "center" && answer.distance === "near") {
        await speak(words[lang].in_reach);
        stop_find(false);
        break;
      }
    } else {
      misses += 1;
      beep(260, 0.06, 0, 0.15);
      // do not repeat the hint every round, it gets tiring
      if (misses % 3 === 1 || answer.hazard || answer.error) await present(answer);
    }
    await wait(600);
  }
}

function stop_find(announce = true) {
  finding = false;
  mark_active(null);
  keep_screen_on(false);
  if (announce) {
    show(words[lang].stopped);
    speak(words[lang].stopped);
  }
}

async function keep_screen_on(on) {
  try {
    if (on && "wakeLock" in navigator) wake_lock = await navigator.wakeLock.request("screen");
    else if (!on && wake_lock) {
      await wake_lock.release();
      wake_lock = null;
    }
  } catch (err) {
    // not supported everywhere, the app works without it
  }
}

// language

function apply_lang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-en]").forEach((el) => {
    el.textContent = el.dataset[lang];
  });
  lang_button.textContent = words[lang].lang_name;
  lang_button.setAttribute("aria-label", words[lang].lang_label);
  apply_directions();
  try {
    localStorage.setItem("gemmasight-lang", lang);
  } catch (err) {
    // fine to forget the choice
  }
}

function toggle_lang() {
  lang = lang === "en" ? "sw" : "en";
  apply_lang();
  speak(words[lang].lang_name);
}

// directions

function current_directions() {
  return chosen_directions || default_directions[lang];
}

function apply_directions() {
  const style = current_directions();
  directions_button.textContent = words[lang][style + "_button"];
  directions_button.setAttribute("aria-label", words[lang][style + "_label"]);
}

function toggle_directions() {
  chosen_directions = current_directions() === "clock" ? "words" : "clock";
  apply_directions();
  try {
    localStorage.setItem("gemmasight-directions", chosen_directions);
  } catch (err) {
    // fine to forget the choice
  }
  // say an example so the user hears what they picked
  speak(words[lang][chosen_directions + "_said"]);
}

function repeat_last() {
  speak(last_speech || words[lang].ready);
}

// start up

document.getElementById("start").addEventListener("click", async () => {
  // audio and speech need a tap before browsers allow them
  const audio_class = window.AudioContext || window.webkitAudioContext;
  if (audio_class) audio = new audio_class();
  document.getElementById("start").remove();
  document.getElementById("app").hidden = false;
  apply_lang();
  try {
    await start_camera();
    show(words[lang].ready);
    await speak(words[lang].ready);
  } catch (err) {
    console.warn(err);
    show(words[lang].no_camera, "hazard");
    await speak(words[lang].no_camera);
  }
});

document.querySelectorAll(".mode").forEach((button) => {
  button.addEventListener("click", () => run_mode(button.dataset.mode));
});
document.getElementById("repeat").addEventListener("click", repeat_last);
lang_button.addEventListener("click", toggle_lang);
directions_button.addEventListener("click", toggle_directions);

document.addEventListener("keydown", (event) => {
  if (event.target.tagName === "INPUT" || event.repeat) return;
  const by_key = { "1": "read", "2": "describe", "3": "find", "4": "ask" };
  if (by_key[event.key]) run_mode(by_key[event.key]);
  else if (event.key === "r") repeat_last();
  else if (event.key === "l") toggle_lang();
  else if (event.key === "d") toggle_directions();
  else if (event.key === "Escape" && stop_listening) stop_listening();
  else if (event.key === "Escape" && finding) stop_find();
});

if (window.speechSynthesis) speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
