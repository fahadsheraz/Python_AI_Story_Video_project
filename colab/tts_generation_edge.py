# AI Story Video Project - Colab TTS Generation
#
# Module 6: Text-to-Speech
#
# This notebook reads segmentation.json and generates:
# - narration audio per scene
# - dialogue audio per character per scene
# - audio_manifest.json for the next modules


# %% [markdown]
# # Module 6: TTS Generation
#
# Output folder:
#
# ```text
# output/audio/
# ```


# %%
from google.colab import drive
drive.mount("/content/drive", force_remount=True)


# %%
!pip install -q edge-tts


# %%
import asyncio
import json
import re
import time
from pathlib import Path

JOB_ID = "job_0011"
PROJECT_ROOT = Path("/content/drive/MyDrive/AI_Story_Video_Project")
JOB_DIR = PROJECT_ROOT / "jobs" / JOB_ID
INPUT_JSON = JOB_DIR / "input" / "segmentation.json"
AUDIO_DIR = JOB_DIR / "output" / "audio"
STATUS_JSON = JOB_DIR / "status.json"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)

print("Input exists:", INPUT_JSON.exists())
print("Audio folder:", AUDIO_DIR)


# %%
with INPUT_JSON.open("r", encoding="utf-8") as file:
    segmentation = json.load(file)

print("Title:", segmentation.get("title"))
print("Scenes:", len(segmentation.get("scenes", [])))
print("Characters:", [character["name"] for character in segmentation.get("characters", [])])


# %%
import edge_tts

NARRATOR_VOICE = "en-GB-RyanNeural"

CHARACTER_VOICES = {
    "Sara": "en-US-JennyNeural",
    "Ali": "en-US-GuyNeural",
    "Maya": "en-US-JennyNeural",
    "Ayan": "en-US-GuyNeural",
}

DEFAULT_CHARACTER_VOICES = [
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-US-AriaNeural",
    "en-US-DavisNeural",
    "en-GB-SoniaNeural",
]


VOICE_STYLE = {
    "narration": {"rate": "-5%", "pitch": "+0Hz"},
    "dialogue": {"rate": "+0%", "pitch": "+0Hz"},
    "curious": {"rate": "+3%", "pitch": "+0Hz"},
    "urgent": {"rate": "+6%", "pitch": "+0Hz"},
    "serious": {"rate": "-4%", "pitch": "+0Hz"},
}

FALLBACK_VOICE = "en-GB-RyanNeural"


def voice_for_character(name):
    if name in CHARACTER_VOICES:
        return CHARACTER_VOICES[name]

    existing_names = sorted({character.get("name", "") for character in segmentation.get("characters", [])})
    try:
        index = existing_names.index(name)
    except ValueError:
        index = 0

    return DEFAULT_CHARACTER_VOICES[index % len(DEFAULT_CHARACTER_VOICES)]


def safe_name(value):
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return cleaned.strip("_") or "unknown"


def prepare_tts_text(text, clip_type="dialogue"):
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace('"', "")
    cleaned = cleaned.replace("'", "")
    if clip_type == "narration":
        return cleaned
    return cleaned


async def synthesize_with_style(text, voice, output_path, style_name):
    style = VOICE_STYLE.get(style_name, VOICE_STYLE["dialogue"])
    attempts = [
        {"voice": voice, "rate": style["rate"], "pitch": style["pitch"]},
        {"voice": voice, "rate": "+0%", "pitch": "+0Hz"},
        {"voice": FALLBACK_VOICE, "rate": "+0%", "pitch": "+0Hz"},
    ]

    last_error = None
    for index, attempt in enumerate(attempts, start=1):
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=attempt["voice"],
                rate=attempt["rate"],
                pitch=attempt["pitch"],
            )
            await communicate.save(str(output_path))
            if output_path.exists() and output_path.stat().st_size > 0:
                return attempt["voice"]
        except Exception as error:
            last_error = error
            print("TTS retry", index, "failed:", error)
            time.sleep(1)

    raise RuntimeError(f"TTS failed for {output_path.name}: {last_error}")


# %%
audio_manifest = []

for scene in segmentation.get("scenes", []):
    scene_number = scene.get("scene_number")

    narration = scene.get("narration", "").strip()
    if narration:
        output_path = AUDIO_DIR / f"scene_{scene_number:02d}_narration.mp3"
        print("Narration:", output_path.name)
        used_voice = await synthesize_with_style(
            prepare_tts_text(narration, "narration"),
            NARRATOR_VOICE,
            output_path,
            "narration",
        )
        audio_manifest.append({
            "scene_number": scene_number,
            "sequence": len(audio_manifest) + 1,
            "type": "narration",
            "speaker": "Narrator",
            "voice": used_voice,
            "text": narration,
            "audio_path": str(output_path),
        })

    dialogue_index_by_speaker = {}

    for dialogue in scene.get("dialogues", []):
        speaker = dialogue.get("speaker", "Unknown")
        text = dialogue.get("text", "").strip()
        if not text:
            continue

        dialogue_index_by_speaker[speaker] = dialogue_index_by_speaker.get(speaker, 0) + 1
        dialogue_index = dialogue_index_by_speaker[speaker]
        voice = voice_for_character(speaker)
        emotion = dialogue.get("emotion", "neutral")
        output_path = AUDIO_DIR / (
            f"scene_{scene_number:02d}_{safe_name(speaker)}_{dialogue_index:02d}.mp3"
        )

        print("Dialogue:", speaker, "->", output_path.name)
        used_voice = await synthesize_with_style(
            prepare_tts_text(text, "dialogue"),
            voice,
            output_path,
            emotion,
        )
        audio_manifest.append({
            "scene_number": scene_number,
            "sequence": len(audio_manifest) + 1,
            "type": "dialogue",
            "speaker": speaker,
            "voice": used_voice,
            "emotion": emotion,
            "text": text,
            "audio_path": str(output_path),
        })

print("Audio files generated:", len(audio_manifest))


# %%
MANIFEST_JSON = AUDIO_DIR / "audio_manifest.json"

with MANIFEST_JSON.open("w", encoding="utf-8") as file:
    json.dump(audio_manifest, file, indent=2, ensure_ascii=False)

status = {
    "job_id": JOB_ID,
    "status": "module_6_completed",
    "step": "tts_audio_generated",
    "progress": 100,
    "audio_manifest_path": str(MANIFEST_JSON),
}

with STATUS_JSON.open("w", encoding="utf-8") as file:
    json.dump(status, file, indent=2, ensure_ascii=False)

print("Saved manifest:", MANIFEST_JSON)
print("Updated status:", STATUS_JSON)
