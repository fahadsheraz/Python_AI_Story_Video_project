# AI Story Video Project - Simple Video Composition
#
# Modules 8-10 MVP:
# - combines backgrounds
# - overlays character portraits
# - joins narration/dialogue audio per scene
# - exports a final MP4
#
# This is an animatic MVP, not full lip-sync yet.


# %% [markdown]
# # Simple Scene Composition + Video Rendering
#
# Input folders:
#
# ```text
# output/characters/
# output/backgrounds/
# output/audio/
# ```
#
# Output:
#
# ```text
# output/video/final_animatic.mp4
# ```


# %%
from google.colab import drive
drive.mount("/content/drive", force_remount=True)


# %%
!apt-get -qq update
!apt-get -qq install -y ffmpeg
!pip install -q pillow moviepy


# %%
import json
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

JOB_ID = "job_0011"
PROJECT_ROOT = Path("/content/drive/MyDrive/AI_Story_Video_Project")
JOB_DIR = PROJECT_ROOT / "jobs" / JOB_ID
INPUT_JSON = JOB_DIR / "input" / "segmentation.json"
CHARACTER_DIR = JOB_DIR / "output" / "characters"
BACKGROUND_DIR = JOB_DIR / "output" / "backgrounds"
AUDIO_DIR = JOB_DIR / "output" / "audio"
VIDEO_DIR = JOB_DIR / "output" / "video"
STATUS_JSON = JOB_DIR / "status.json"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)

print("Input exists:", INPUT_JSON.exists())
print("Character dir:", CHARACTER_DIR.exists())
print("Background dir:", BACKGROUND_DIR.exists())
print("Audio dir:", AUDIO_DIR.exists())


# %%
with INPUT_JSON.open("r", encoding="utf-8") as file:
    segmentation = json.load(file)

AUDIO_MANIFEST = AUDIO_DIR / "audio_manifest.json"
CHARACTER_MANIFEST = CHARACTER_DIR / "characters_manifest.json"
SPRITE_MANIFEST = CHARACTER_DIR / "sprites" / "sprites_manifest.json"

with AUDIO_MANIFEST.open("r", encoding="utf-8") as file:
    audio_manifest = json.load(file)

if SPRITE_MANIFEST.exists():
    with SPRITE_MANIFEST.open("r", encoding="utf-8") as file:
        character_manifest = json.load(file)
    character_images = {
        item["name"]: Path(item["sprite_path"])
        for item in character_manifest
    }
else:
    with CHARACTER_MANIFEST.open("r", encoding="utf-8") as file:
        character_manifest = json.load(file)
    character_images = {
        item["name"]: Path(item["image_path"])
        for item in character_manifest
    }

print("Scenes:", len(segmentation.get("scenes", [])))
print("Audio clips:", len(audio_manifest))
print("Character images:", character_images)


# %%
def run_command(command):
    print("Running:", " ".join(str(part) for part in command))
    subprocess.run(command, check=True)


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


def scene_audio_items(scene_number):
    items = [
        item
        for item in audio_manifest
        if item.get("scene_number") == scene_number
    ]
    return sorted(items, key=lambda item: item.get("sequence", 0))


def concat_audio_for_scene(scene_number, items):
    list_path = VIDEO_DIR / f"scene_{scene_number:02d}_audio_list.txt"
    output_path = VIDEO_DIR / f"scene_{scene_number:02d}_audio.mp3"

    with list_path.open("w", encoding="utf-8") as file:
        for item in items:
            audio_path = Path(item["audio_path"])
            file.write(f"file '{audio_path}'\n")

    run_command([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(output_path),
    ])

    return output_path


def cover_image(image, size):
    target_w, target_h = size
    image = image.convert("RGB")
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize((math.ceil(image.width * scale), math.ceil(image.height * scale)))
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def paste_character(canvas, character_path, x, y, height):
    if not character_path.exists():
        return None

    character = Image.open(character_path).convert("RGBA")
    character = crop_visible_character(character)
    scale = height / character.height
    width = int(character.width * scale)
    character = character.resize((width, height))

    x = max(24, min(x, canvas.width - width - 24))
    y = max(12, min(y, canvas.height - height - 96))

    shadow = Image.new("RGBA", character.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((width * 0.2, height * 0.88, width * 0.8, height * 0.98), fill=(0, 0, 0, 80))

    canvas.alpha_composite(shadow, (x, y))
    canvas.alpha_composite(character, (x, y))
    return x, y, width, height


def crop_visible_character(image):
    image = image.convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        return image

    left, top, right, bottom = bbox
    pad_x = max(8, int((right - left) * 0.04))
    pad_y = max(8, int((bottom - top) * 0.025))
    bbox = (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(image.width, right + pad_x),
        min(image.height, bottom + pad_y),
    )
    return image.crop(bbox)


def draw_caption(canvas, text):
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    margin = 28
    box_height = 72
    y = canvas.height - box_height - margin
    draw.rounded_rectangle(
        (margin, y, canvas.width - margin, y + box_height),
        radius=10,
        fill=(0, 0, 0, 150),
    )
    draw.text((margin + 18, y + 22), text[:160], fill=(255, 255, 255, 255), font=font)


def character_position(slot, scene_number=1, index=0, active=False, depth="midground", scale=1.0):
    scene_variants = [
        {
            "left": (300, 160, 500),
            "right": (770, 165, 500),
            "center": (505, 150, 520),
            "background": (555, 230, 360),
        },
        {
            "left": (210, 170, 470),
            "right": (850, 170, 470),
            "center": (520, 165, 500),
            "background": (605, 245, 340),
        },
        {
            "left": (360, 150, 520),
            "right": (720, 155, 520),
            "center": (520, 140, 540),
            "background": (610, 240, 330),
        },
    ]
    base = scene_variants[(scene_number - 1) % len(scene_variants)].get(slot, (520, 230, 360))

    x, y, height = base
    if depth == "foreground":
        height = int(height * 1.08)
        y -= 28
    elif depth == "background":
        height = int(height * 0.78)
        y += 45

    x += (index % 2) * 16 - 8
    height = int(height * scale)

    if active:
        return x - 20, y - 20, int(height * 1.10)
    return x, y, height


def dim_inactive_character(canvas, x, y, width, height):
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 52))
    canvas.alpha_composite(overlay, (x, y))


def caption_for_clip(scene, active_speaker=None, clip_type="narration", clip_text=""):
    if clip_text:
        if clip_type == "dialogue" and active_speaker:
            return f"{active_speaker}: {clip_text}"
        return clip_text

    if clip_type == "dialogue" and active_speaker:
        for dialogue in scene.get("dialogues", []):
            if dialogue.get("speaker") == active_speaker:
                return f'{active_speaker}: {dialogue.get("text", "")}'
    return scene.get("narration", "")


def create_scene_frame(scene, active_speaker=None, clip_type="narration", clip_text=""):
    scene_number = scene["scene_number"]
    safe_speaker = str(active_speaker or clip_type).lower().replace(" ", "_")
    background_path = BACKGROUND_DIR / f"scene_{scene_number:02d}_background.png"
    frame_path = VIDEO_DIR / f"scene_{scene_number:02d}_{safe_speaker}_frame.png"

    background = Image.open(background_path)
    frame = cover_image(background, (1280, 720)).convert("RGBA")

    characters = scene.get("characters", [])
    layout = scene.get("layout") or {}
    if len(characters) == 1:
        layout.setdefault(characters[0], {"slot": "center"})

    for index, character_name in enumerate(characters[:3]):
        fallback_slot = ["left", "right", "center"][index]
        character_layout = layout.get(character_name, {})
        slot = character_layout.get("slot", fallback_slot)
        depth = character_layout.get("depth", "midground")
        scale = float(character_layout.get("scale", 1.0))
        is_active = clip_type == "dialogue" and character_name == active_speaker
        x, y, height = character_position(slot, scene_number, index, is_active, depth, scale)
        bbox = paste_character(frame, character_images.get(character_name, Path("")), x, y, height)

        if bbox and clip_type == "dialogue" and active_speaker and not is_active:
            dim_inactive_character(frame, *bbox)

    draw_caption(frame, caption_for_clip(scene, active_speaker, clip_type, clip_text))
    frame.convert("RGB").save(frame_path)
    return frame_path


# %%
scene_video_paths = []
scene_lookup = {scene["scene_number"]: scene for scene in segmentation.get("scenes", [])}

for scene in segmentation.get("scenes", []):
    scene_number = scene["scene_number"]
    items = scene_audio_items(scene_number)
    scene_clip_paths = []

    for clip_index, item in enumerate(items, start=1):
        audio_path = Path(item["audio_path"])
        duration = audio_duration_seconds(audio_path)
        frame = create_scene_frame(
            scene,
            active_speaker=item.get("speaker"),
            clip_type=item.get("type", "dialogue"),
            clip_text=item.get("text", ""),
        )
        scene_clip = VIDEO_DIR / f"scene_{scene_number:02d}_clip_{clip_index:02d}.mp4"

        run_command([
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(frame),
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-t",
            f"{duration:.3f}",
            "-vf",
            "scale=1280:720,zoompan=z='min(zoom+0.0008,1.035)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=25",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(scene_clip),
        ])

        scene_clip_paths.append(scene_clip)

    scene_video = VIDEO_DIR / f"scene_{scene_number:02d}.mp4"
    scene_list = VIDEO_DIR / f"scene_{scene_number:02d}_clip_list.txt"
    with scene_list.open("w", encoding="utf-8") as file:
        for path in scene_clip_paths:
            file.write(f"file '{path}'\n")

    run_command([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(scene_list),
        "-c",
        "copy",
        str(scene_video),
    ])

    scene_video_paths.append(scene_video)

print("Scene videos:", scene_video_paths)


# %%
FINAL_VIDEO = VIDEO_DIR / "final_animatic.mp4"
video_list = VIDEO_DIR / "video_list.txt"

with video_list.open("w", encoding="utf-8") as file:
    for path in scene_video_paths:
        file.write(f"file '{path}'\n")

run_command([
    "ffmpeg",
    "-y",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    str(video_list),
    "-c",
    "copy",
    str(FINAL_VIDEO),
])

status = {
    "job_id": JOB_ID,
    "status": "module_10_completed",
    "step": "final_animatic_rendered",
    "progress": 100,
    "video_path": str(FINAL_VIDEO),
}

with STATUS_JSON.open("w", encoding="utf-8") as file:
    json.dump(status, file, indent=2, ensure_ascii=False)

print("Final video:", FINAL_VIDEO)
