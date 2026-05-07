# AI Story Video Project - Lip Sync Preparation
#
# Module 7 starter:
# - reads dialogue audio
# - estimates speech timing
# - creates mouth cue JSON per dialogue
#
# This is a lightweight prep step. True face animation can later use Wav2Lip,
# SadTalker, LivePortrait, or another animation model.


# %% [markdown]
# # Lip Sync Preparation
#
# Output:
#
# ```text
# output/lipsync/
# ```


# %%
from google.colab import drive
drive.mount("/content/drive", force_remount=True)


# %%
!apt-get -qq update
!apt-get -qq install -y ffmpeg


# %%
import json
import subprocess
from pathlib import Path

JOB_ID = "job_0011"
PROJECT_ROOT = Path("/content/drive/MyDrive/AI_Story_Video_Project")
JOB_DIR = PROJECT_ROOT / "jobs" / JOB_ID
AUDIO_DIR = JOB_DIR / "output" / "audio"
LIPSYNC_DIR = JOB_DIR / "output" / "lipsync"
STATUS_JSON = JOB_DIR / "status.json"

LIPSYNC_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_MANIFEST = AUDIO_DIR / "audio_manifest.json"

print("Audio manifest exists:", AUDIO_MANIFEST.exists())


# %%
with AUDIO_MANIFEST.open("r", encoding="utf-8") as file:
    audio_manifest = json.load(file)

dialogue_items = [item for item in audio_manifest if item.get("type") == "dialogue"]

print("Dialogue clips:", len(dialogue_items))


# %%
def audio_duration_seconds(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def build_mouth_cues(text, duration):
    words = [word for word in text.split() if word.strip()]
    if not words:
        return []

    cue_count = max(1, min(len(words), int(duration * 5)))
    step = duration / cue_count
    cues = []

    mouth_shapes = ["closed", "open_small", "open_wide", "smile", "round"]
    for index in range(cue_count):
        cues.append({
            "start": round(index * step, 3),
            "end": round((index + 1) * step, 3),
            "mouth": mouth_shapes[index % len(mouth_shapes)],
        })

    return cues


lipsync_manifest = []

for index, item in enumerate(dialogue_items, start=1):
    audio_path = Path(item["audio_path"])
    duration = audio_duration_seconds(audio_path)
    cue_path = LIPSYNC_DIR / f"scene_{item['scene_number']:02d}_{item['speaker'].lower()}_{index:02d}_mouth_cues.json"
    cues = build_mouth_cues(item.get("text", ""), duration)

    payload = {
        "scene_number": item["scene_number"],
        "speaker": item["speaker"],
        "text": item["text"],
        "audio_path": str(audio_path),
        "duration": duration,
        "mouth_cues": cues,
    }

    with cue_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    lipsync_manifest.append({
        "scene_number": item["scene_number"],
        "speaker": item["speaker"],
        "audio_path": str(audio_path),
        "cue_path": str(cue_path),
        "duration": duration,
    })

print("Mouth cue files:", len(lipsync_manifest))


# %%
MANIFEST_JSON = LIPSYNC_DIR / "lipsync_manifest.json"

with MANIFEST_JSON.open("w", encoding="utf-8") as file:
    json.dump(lipsync_manifest, file, indent=2, ensure_ascii=False)

status = {
    "job_id": JOB_ID,
    "status": "module_7_prep_completed",
    "step": "mouth_cues_generated",
    "progress": 100,
    "lipsync_manifest_path": str(MANIFEST_JSON),
}

with STATUS_JSON.open("w", encoding="utf-8") as file:
    json.dump(status, file, indent=2, ensure_ascii=False)

print("Saved lipsync manifest:", MANIFEST_JSON)
print("Updated status:", STATUS_JSON)
