import json

# where the object sits across the frame, as a clock position
# the camera only sees what is ahead, so the range runs from 10 to 2
clock_by_position = {
    "left": 10,
    "slightly left": 11,
    "center": 12,
    "slightly right": 1,
    "right": 2,
}

# plain left and right words for users who do not think in clock positions
words_by_position = {
    "en": {
        "left": "to your left",
        "slightly left": "slightly to your left",
        "center": "straight ahead",
        "slightly right": "slightly to your right",
        "right": "to your right",
    },
    "sw": {
        "left": "upande wa kushoto",
        "slightly left": "kushoto kidogo",
        "center": "moja kwa moja mbele yako",
        "slightly right": "kulia kidogo",
        "right": "upande wa kulia",
    },
}

# swahili time telling uses a different clock, so words are the default there
# and the clock phrase says clock face to make clear it is not the time of day
default_style = {"en": "clock", "sw": "words"}

distance_words = {
    "en": {"near": "within reach", "mid": "a few steps away", "far": "far away"},
    "sw": {"near": "karibu sana", "mid": "hatua chache", "far": "mbali"},
}

def steps_phrase(steps, lang):
    # always worded as about, a single camera can only estimate distance
    if steps == 0:
        return distance_words[lang]["near"]
    if lang == "sw":
        return f"takriban hatua {steps}"
    return f"about {steps} step away" if steps == 1 else f"about {steps} steps away"


def as_steps(value):
    # the model may send 3, 3.5 or "3", anything else is ignored
    try:
        steps = round(float(value))
    except (TypeError, ValueError):
        return None
    if steps < 0 or steps > 50:
        return None
    return steps


def band_for_steps(steps):
    # turn steps into the near, mid and far bands that drive beep pitch and the auto stop
    if steps == 0:
        return "near"
    if steps <= 4:
        return "mid"
    return "far"


not_found_words = {
    "en": "Not in view yet. Turn slowly.",
    "sw": "Bado sikioni. Geuka polepole.",
}

unclear_words = {
    "en": "Sorry, I could not understand that picture. Please try again.",
    "sw": "Samahani, sikuelewa picha hiyo. Tafadhali jaribu tena.",
}


def extract_json(text):
    # the model sometimes wraps its answer in prose or code fences
    # so try every opening brace and keep the last object that decodes
    decoder = json.JSONDecoder()
    found = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(value, dict):
            found = value
    return found


def as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return False


def direction_phrase(position, lang, style=None):
    position = (position or "").strip().lower()
    if position not in clock_by_position:
        return ""
    style = style or default_style[lang]
    if style == "words":
        return words_by_position[lang][position]
    hour = clock_by_position[position]
    if lang == "sw":
        return f"saa {hour} kwenye uso wa saa"
    return f"at {hour} o'clock"


def build_answer(mode, raw_text, lang, directions=None):
    # turn the model reply into one short thing to say plus cues for sound and vibration
    data = extract_json(raw_text or "")
    if data is None:
        # no json at all, fall back to the plain text if there is any
        speech = (raw_text or "").strip().strip("`").strip()
        return {
            "speech": speech[:400] or unclear_words[lang],
            "hazard": False,
            "found": False,
            "position": None,
            "clock": None,
            "distance": None,
            "steps": None,
        }

    position = str(data.get("position") or "").strip().lower() or None
    if position not in clock_by_position:
        position = None
    distance = str(data.get("distance") or "").strip().lower() or None
    if distance not in distance_words["en"]:
        distance = None
    steps = as_steps(data.get("steps"))
    if steps is not None:
        # steps are the finer estimate, so the band follows them
        distance = band_for_steps(steps)

    answer = {
        "speech": str(data.get("speech") or "").strip(),
        "hazard": as_bool(data.get("hazard")),
        "found": as_bool(data.get("found")),
        "position": position,
        "clock": clock_by_position.get(position) if position else None,
        "distance": distance,
        "steps": steps,
    }

    if mode == "read":
        # a printed warning on a label is read out, it should not set off the hazard alarm
        answer["hazard"] = False

    if mode == "find":
        if answer["found"]:
            # the direction comes from our own mapping so it is always said the same way
            label = str(data.get("label") or "").strip() or ("It" if lang == "en" else "Kitu")
            parts = [label]
            direction = direction_phrase(position, lang, directions)
            if direction:
                parts.append(direction)
            if steps is not None:
                parts.append(steps_phrase(steps, lang))
            elif distance:
                parts.append(distance_words[lang][distance])
            answer["speech"] = ", ".join(parts) + "."
        else:
            answer["position"] = None
            answer["clock"] = None
            answer["distance"] = None
            answer["steps"] = None
            answer["speech"] = answer["speech"] or not_found_words[lang]

    if not answer["speech"]:
        answer["speech"] = unclear_words[lang]
    return answer
