from app.guidance import build_answer, direction_phrase, extract_json
from app.everyday_items import everyday_items
from app.prompts import build_prompt


def test_extract_json_from_fenced_reply():
    text = 'Sure!\n```json\n{"speech": "A red mug", "hazard": false}\n```'
    assert extract_json(text) == {"speech": "A red mug", "hazard": False}


def test_extract_json_keeps_last_object():
    text = 'thinking {"draft": 1} then {"speech": "final"}'
    assert extract_json(text) == {"speech": "final"}


def test_extract_json_none_when_missing():
    assert extract_json("no json here") is None


def test_direction_phrase_english_uses_clock():
    assert direction_phrase("slightly left", "en") == "at 11 o'clock"
    assert direction_phrase("center", "en") == "at 12 o'clock"
    assert direction_phrase("right", "en") == "at 2 o'clock"


def test_direction_phrase_swahili_uses_words():
    assert direction_phrase("left", "sw") == "upande wa kushoto"


def test_direction_phrase_english_words_when_chosen():
    assert direction_phrase("slightly left", "en", "words") == "slightly to your left"
    assert direction_phrase("center", "en", "words") == "straight ahead"


def test_direction_phrase_swahili_clock_when_chosen():
    assert direction_phrase("right", "sw", "clock") == "saa 2 kwenye uso wa saa"


def test_find_uses_chosen_direction_style():
    raw = '{"found": true, "label": "bag", "position": "left", "distance": "mid"}'
    answer = build_answer("find", raw, "en", "words")
    assert answer["speech"] == "bag, to your left, a few steps away."
    # the clock number is still sent back for the panned beep
    assert answer["clock"] == 10


def test_find_says_steps_when_given():
    raw = '{"found": true, "label": "mouse", "position": "slightly left", "distance": "mid", "steps": 3}'
    answer = build_answer("find", raw, "en")
    assert answer["speech"] == "mouse, at 11 o'clock, about 3 steps away."
    assert answer["steps"] == 3


def test_find_one_step_is_singular():
    raw = '{"found": true, "label": "door", "position": "center", "steps": "1"}'
    assert build_answer("find", raw, "en")["speech"] == "door, at 12 o'clock, about 1 step away."


def test_find_zero_steps_is_within_reach_and_near():
    raw = '{"found": true, "label": "cup", "position": "center", "distance": "far", "steps": 0}'
    answer = build_answer("find", raw, "en")
    assert answer["speech"] == "cup, at 12 o'clock, within reach."
    # steps win over the rough band, so the auto stop and beep pitch follow them
    assert answer["distance"] == "near"


def test_find_steps_in_swahili():
    raw = '{"found": true, "label": "kiti", "position": "right", "steps": 4.4}'
    assert build_answer("find", raw, "sw")["speech"] == "kiti, upande wa kulia, takriban hatua 4."


def test_find_bad_steps_fall_back_to_band():
    raw = '{"found": true, "label": "bag", "position": "left", "distance": "far", "steps": "lots"}'
    answer = build_answer("find", raw, "en")
    assert answer["steps"] is None
    assert answer["speech"] == "bag, at 10 o'clock, far away."


def test_far_steps_set_far_band():
    raw = '{"found": true, "label": "gate", "position": "center", "steps": 12}'
    assert build_answer("find", raw, "en")["distance"] == "far"


def test_prompts_ask_for_steps_where_useful():
    for mode in ("describe", "find", "ask"):
        prompt = build_prompt(mode, "keys", "en")
        assert "70 cm" in prompt
        assert "{steps_line}" not in prompt
    assert "70 cm" not in build_prompt("read", "", "en")


def test_direction_phrase_unknown_is_empty():
    assert direction_phrase("behind", "en") == ""


def test_find_found_builds_speech_from_fields():
    raw = '{"found": true, "label": "keys", "position": "slightly right", "distance": "near", "speech": "ignored"}'
    answer = build_answer("find", raw, "en")
    assert answer["found"] is True
    assert answer["clock"] == 1
    assert answer["speech"] == "keys, at 1 o'clock, within reach."


def test_find_found_in_swahili():
    raw = '{"found": true, "label": "funguo", "position": "center", "distance": "mid"}'
    answer = build_answer("find", raw, "sw")
    assert answer["speech"] == "funguo, moja kwa moja mbele yako, hatua chache."


def test_find_not_found_clears_position_and_gives_hint():
    raw = '{"found": false, "position": "left", "distance": "far", "speech": ""}'
    answer = build_answer("find", raw, "en")
    assert answer["found"] is False
    assert answer["position"] is None
    assert answer["clock"] is None
    assert answer["speech"] == "Not in view yet. Turn slowly."


def test_bad_position_and_distance_are_dropped():
    raw = '{"found": true, "label": "cup", "position": "upper left", "distance": "2 meters"}'
    answer = build_answer("find", raw, "en")
    assert answer["position"] is None
    assert answer["distance"] is None
    assert answer["speech"] == "cup."


def test_hazard_string_is_read_as_bool():
    answer = build_answer("describe", '{"speech": "Step down ahead", "hazard": "true"}', "en")
    assert answer["hazard"] is True


def test_read_never_raises_hazard():
    answer = build_answer("read", '{"speech": "Warning, do not exceed 8 tablets", "hazard": true}', "en")
    assert answer["hazard"] is False


def test_plain_text_reply_is_still_spoken():
    answer = build_answer("read", "Panadol 500 mg", "en")
    assert answer["speech"] == "Panadol 500 mg"


def test_empty_reply_gives_retry_message():
    answer = build_answer("describe", "", "sw")
    assert "jaribu tena" in answer["speech"]


def test_prompt_includes_target_and_language():
    prompt = build_prompt("find", 'my "blue" bag', "sw")
    assert "my 'blue' bag" in prompt
    assert "Kiswahili" in prompt
    assert "{text}" not in prompt


def test_read_prompt_mentions_medicine_safety():
    assert "never guess" in build_prompt("read", "", "en")


def test_read_prompt_lists_every_everyday_item():
    prompt = build_prompt("read", "", "en")
    for name, _ in everyday_items:
        assert f"- {name}:" in prompt
    assert "{items}" not in prompt
    assert '{"speech": string, "hazard": false}' in prompt


def test_read_prompt_protects_pins():
    assert "PIN" in build_prompt("read", "", "en")
