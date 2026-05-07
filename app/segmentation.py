from __future__ import annotations

import re
from collections import OrderedDict
from uuid import uuid4

QUOTE_PATTERN = re.compile(
    r'(?P<speaker>[A-Z][A-Za-z ]{1,40})\s*'
    r'(?:said|asked|replied|shouted|whispered|answered|cried|told)\s*,?\s*'
    r'["](?P<text>[^"]+)["]',
    re.IGNORECASE,
)
SIMPLE_QUOTE_PATTERN = re.compile(r'["](?P<text>[^"]+)["]')
NAME_PATTERN = re.compile(r"\b[A-Z][a-z]{2,}\b")

COMMON_WORDS = {
    "The",
    "This",
    "That",
    "Then",
    "When",
    "After",
    "Before",
    "Scene",
    "Chapter",
    "Suddenly",
    "Meanwhile",
    "Later",
    "Morning",
    "Evening",
    "Night",
    "He",
    "She",
    "They",
    "Them",
    "His",
    "Her",
    "Their",
    "Someone",
}


def segment_story(title: str, story: str) -> dict:
    """Create editable scene data from a story using deterministic local rules."""
    cleaned_story = _normalize_text(story)
    scene_chunks = _split_into_scenes(cleaned_story)
    known_characters: OrderedDict[str, dict] = OrderedDict()
    scenes: list[dict] = []

    for index, chunk in enumerate(scene_chunks, start=1):
        dialogues = _extract_dialogues(chunk)
        character_names = _extract_character_names(chunk, dialogues)

        for name in character_names:
            if name not in known_characters:
                known_characters[name] = {
                    "id": _new_id("char"),
                    "name": name,
                    "description": "",
                    "role": "Story character",
                }

        scenes.append({
            "id": _new_id("scene"),
            "scene_number": index,
            "title": f"Scene {index}",
            "location": _guess_location(chunk),
            "time_of_day": _guess_time_of_day(chunk),
            "mood": _guess_mood(chunk),
            "key_objects": _extract_key_objects(chunk),
            "narration": _extract_narration(chunk),
            "characters": character_names,
            "dialogues": dialogues,
            "background_prompt": _build_background_prompt(index, chunk),
            "layout": _build_scene_layout(character_names, index, chunk),
            "notes": "Auto segmented. Please review before confirming.",
        })

    return {
        "title": title.strip() or "Untitled Story",
        "status": "draft",
        "characters": list(known_characters.values()),
        "scenes": scenes,
    }


def _normalize_text(story: str) -> str:
    return re.sub(r"\s+", " ", story).strip()


def _split_into_scenes(story: str) -> list[str]:
    if not story:
        return []

    explicit = re.split(r"\b(?:Scene|Chapter)\s+\d+\s*[:.-]?\s*", story, flags=re.IGNORECASE)
    explicit = [part.strip() for part in explicit if part.strip()]
    if len(explicit) >= 1 and re.match(r"\s*(?:Scene|Chapter)\s+\d+", story, flags=re.IGNORECASE):
        return explicit

    sentences = re.split(r"(?<=[.!?])\s+", story)
    chunks: list[str] = []
    current: list[str] = []

    for sentence in sentences:
        if not sentence.strip():
            continue
        current.append(sentence.strip())
        if len(current) >= 4:
            chunks.append(" ".join(current))
            current = []

    if current:
        chunks.append(" ".join(current))

    return chunks or [story]


def _extract_dialogues(scene_text: str) -> list[dict]:
    dialogues: list[dict] = []
    used_spans: list[tuple[int, int]] = []
    dialogue_number = 1

    for match in QUOTE_PATTERN.finditer(scene_text):
        speaker = _clean_name(match.group("speaker"))
        text = match.group("text").strip()
        if speaker and text:
            dialogues.append({
                "id": _new_id("dlg"),
                "dialogue_number": dialogue_number,
                "speaker": speaker,
                "text": text,
                "emotion": _guess_dialogue_emotion(text),
            })
            dialogue_number += 1
            used_spans.append(match.span("text"))

    for match in SIMPLE_QUOTE_PATTERN.finditer(scene_text):
        if _span_inside_any(match.span("text"), used_spans):
            continue
        text = match.group("text").strip()
        if text:
            dialogues.append({
                "id": _new_id("dlg"),
                "dialogue_number": dialogue_number,
                "speaker": "Unknown",
                "text": text,
                "emotion": _guess_dialogue_emotion(text),
            })
            dialogue_number += 1

    return dialogues


def _extract_character_names(scene_text: str, dialogues: list[dict]) -> list[str]:
    names: OrderedDict[str, None] = OrderedDict()
    narration_text = _extract_narration(scene_text)

    for dialogue in dialogues:
        speaker = dialogue.get("speaker", "Unknown")
        if speaker != "Unknown":
            names[speaker] = None

    for match in NAME_PATTERN.finditer(narration_text):
        name = _clean_name(match.group(0))
        if name and name not in COMMON_WORDS:
            names[name] = None

    return list(names.keys())


def _extract_narration(scene_text: str) -> str:
    narration = QUOTE_PATTERN.sub("", scene_text)
    narration = SIMPLE_QUOTE_PATTERN.sub("", narration)
    narration = re.sub(r"\s+", " ", narration).strip(" -,.")
    return narration


def _guess_location(scene_text: str) -> str:
    lowered = scene_text.lower()
    known_locations = [
        "old library",
        "library",
        "school",
        "house",
        "room",
        "office",
        "forest",
        "castle",
        "village",
        "city",
        "street",
        "market",
        "cave",
        "garden",
        "hospital",
        "station",
        "spaceship",
    ]
    for location in known_locations:
        if location in lowered:
            return location.title()

    location_match = re.search(r"\b(?:in|inside|at|near)\s+the\s+([A-Za-z ]{3,35})", scene_text, re.IGNORECASE)
    if not location_match:
        location_match = re.search(r"\b(?:in|inside|at|near)\s+([A-Za-z ]{3,35})", scene_text, re.IGNORECASE)
    if not location_match:
        return ""
    location = location_match.group(1).strip(" .,")
    return " ".join(location.split()[:4]).title()


def _guess_time_of_day(scene_text: str) -> str:
    lowered = scene_text.lower()
    for value in ["morning", "afternoon", "evening", "night", "midnight", "dawn", "sunset"]:
        if value in lowered:
            return value
    return ""


def _guess_mood(scene_text: str) -> str:
    lowered = scene_text.lower()
    if any(word in lowered for word in ["secret", "hidden", "whispered", "dark", "night", "silent"]):
        return "mysterious"
    if any(word in lowered for word in ["shouted", "ran", "danger", "fear", "storm"]):
        return "tense"
    if any(word in lowered for word in ["smiled", "happy", "bright", "morning"]):
        return "warm"
    return "cinematic"


def _extract_key_objects(scene_text: str) -> list[str]:
    lowered = scene_text.lower()
    object_words = [
        "map",
        "notebook",
        "window",
        "table",
        "door",
        "brick",
        "wall",
        "book",
        "bookshelf",
        "lamp",
        "chair",
        "letter",
        "key",
        "box",
        "sword",
        "car",
        "tree",
        "river",
        "bridge",
    ]
    return [word for word in object_words if word in lowered]


def _guess_dialogue_emotion(text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()
    if "?" in stripped:
        return "curious"
    if "!" in stripped:
        return "urgent"
    if any(word in lowered for word in ["stay close", "watching", "secret", "hidden"]):
        return "serious"
    return "neutral"


def _build_background_prompt(scene_number: int, scene_text: str) -> str:
    narration = _extract_narration(scene_text)
    location = _guess_location(scene_text) or "story environment"
    mood = _guess_mood(scene_text)
    key_objects = ", ".join(_extract_key_objects(scene_text)) or "scene objects"
    return (
        f"Empty cinematic background for scene {scene_number}. "
        f"Location: {location}. Mood: {mood}. "
        f"Important objects: {key_objects}. Scene context: {narration}. "
        "No people, no characters, no faces, no text."
    )


def _build_scene_layout(character_names: list[str], scene_number: int, scene_text: str = "") -> dict:
    if len(character_names) == 1:
        slots = ["center"]
    elif scene_number % 2 == 0:
        slots = ["right", "left", "center"]
    else:
        slots = ["left", "right", "center"]

    lowered = scene_text.lower()
    if any(word in lowered for word in ["door", "wall", "stairs", "tunnel"]):
        depth = ["foreground", "midground", "background"]
    elif any(word in lowered for word in ["table", "map", "desk", "locker"]):
        depth = ["midground", "foreground", "background"]
    else:
        depth = ["midground", "midground", "background"]

    return {
        name: {
            "slot": slots[index] if index < len(slots) else "background",
            "depth": depth[index] if index < len(depth) else "background",
            "scale": 1.0 if index < 2 else 0.82,
        }
        for index, name in enumerate(character_names)
    }


def _span_inside_any(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start >= used_start and end <= used_end for used_start, used_end in spans)


def _clean_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name).strip(" ,.-")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else ""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"
