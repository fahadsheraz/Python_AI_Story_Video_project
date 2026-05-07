# AI Story Video Project - Full Body Character Sprites
#
# Module 4 upgrade:
# - generates full-body character images
# - extracts the best single character if model creates a character sheet
# - removes simple studio background while preserving light/white clothes
# - saves transparent PNG sprites for scene composition
#
# Run this after segmentation is confirmed and uploaded to Drive.


# %% [markdown]
# # Full Body Character Sprite Generation
#
# Output:
#
# ```text
# output/characters/sprites/
# ```


# %%
from google.colab import drive
drive.mount("/content/drive", force_remount=True)


# %%
!pip install -q diffusers transformers accelerate safetensors pillow opencv-python


# %%
import json
import re
import torch
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from diffusers import AutoPipelineForText2Image

# Change this if you want to force a specific job.
JOB_ID = "job_0015"
AUTO_USE_LATEST_JOB = True

PROJECT_ROOT = Path("/content/drive/MyDrive/AI_Story_Video_Project")

if AUTO_USE_LATEST_JOB:
    job_folders = sorted((PROJECT_ROOT / "jobs").glob("job_*"))
    job_folders = [
        folder for folder in job_folders
        if (folder / "input" / "segmentation.json").exists()
    ]
    if job_folders:
        JOB_ID = job_folders[-1].name

JOB_DIR = PROJECT_ROOT / "jobs" / JOB_ID
INPUT_JSON = JOB_DIR / "input" / "segmentation.json"
CHARACTER_DIR = JOB_DIR / "output" / "characters"
SPRITE_DIR = CHARACTER_DIR / "sprites"
STATUS_JSON = JOB_DIR / "status.json"

SPRITE_DIR.mkdir(parents=True, exist_ok=True)

print("Job:", JOB_ID)
print("CUDA available:", torch.cuda.is_available())
print("Input exists:", INPUT_JSON.exists())


# %%
with INPUT_JSON.open("r", encoding="utf-8") as file:
    segmentation = json.load(file)

print("Characters:", [character["name"] for character in segmentation.get("characters", [])])


# %%
def safe_name(value):
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return cleaned.strip("_") or "unknown"


def build_full_body_prompt(character):
    name = character.get("name", "Unknown")
    role = character.get("role", "Story character")
    description = character.get("description", "").strip()

    prompt = [
        f"One isolated full body animated film character of {name}.",
        f"Role: {role}.",
        "Only one person in the image.",
        "One single standing pose, front-facing, head to toe visible, feet fully visible.",
        "Centered character with empty margin around the body.",
        "Plain smooth light gray studio background.",
        "No scenery, no room, no window, no furniture, no props.",
        "Not a character sheet, not a reference sheet, not a turnaround sheet.",
        "No side view, no back view, no multiple poses, no duplicate people, no thumbnails.",
        "Clean 3D animated film style, expressive face, simple story character clothing.",
    ]

    if description:
        prompt.append(f"Character description: {description}.")

    return " ".join(prompt)


sprite_prompts = []
for character in segmentation.get("characters", []):
    sprite_prompts.append({
        "character_id": character.get("id"),
        "name": character.get("name"),
        "prompt": build_full_body_prompt(character),
        "raw_image_path": None,
        "sprite_path": None,
        "quality_score": 0,
    })

print(json.dumps(sprite_prompts, indent=2, ensure_ascii=False))


# %%
MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
MAX_ATTEMPTS_PER_CHARACTER = 2

pipe = AutoPipelineForText2Image.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    use_safetensors=True,
)
pipe = pipe.to("cuda")

print("Model loaded")


# %%
NEGATIVE_PROMPT = (
    "portrait, close-up, selfie, cropped head, cropped body, missing legs, missing feet, "
    "extra limbs, extra fingers, bad anatomy, multiple people, duplicate character, "
    "character sheet, reference sheet, turnaround, model sheet, multiple views, "
    "front and side view, side view, back view, repeated character, collage, thumbnails, "
    "room, furniture, window, door, background scene, props, text, logo, watermark, "
    "blurry, low quality"
)


def light_background_mask(rgb):
    max_channel = rgb.max(axis=2)
    min_channel = rgb.min(axis=2)
    spread = max_channel - min_channel

    light_neutral = (max_channel > 178) & (spread < 55)
    studio_gray = (max_channel > 130) & (spread < 28)
    return light_neutral | studio_gray


def crop_best_center_character(raw_image):
    """If the model creates multiple poses, crop the strongest centered full-body candidate."""
    image = raw_image.convert("RGB")
    rgb = np.array(image)
    background = light_background_mask(rgb)
    mask = (~background).astype(np.uint8) * 255

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    candidates = []
    image_center = image.width / 2

    for label in range(1, component_count):
        x, y, width, height, area = stats[label]
        if area < image.width * image.height * 0.015:
            continue
        if height < image.height * 0.35:
            continue

        center_x = x + width / 2
        center_bonus = 1.0 - min(abs(center_x - image_center) / image_center, 1.0)
        height_bonus = min(height / image.height, 1.0)
        aspect = width / max(height, 1)

        # Prefer tall human-like centered figures, but still allow wider clothing/hair.
        shape_bonus = 1.0 if 0.16 <= aspect <= 0.62 else 0.65
        score = area * (1.0 + center_bonus * 1.8) * (1.0 + height_bonus) * shape_bonus
        candidates.append((score, x, y, width, height))

    if not candidates:
        return raw_image

    _, x, y, width, height = max(candidates, key=lambda item: item[0])
    pad_x = int(width * 0.42)
    pad_y = int(height * 0.08)
    left = max(0, x - pad_x)
    top = max(0, y - pad_y)
    right = min(image.width, x + width + pad_x)
    bottom = min(image.height, y + height + pad_y)

    return raw_image.crop((left, top, right, bottom))


def remove_edge_connected_background(image):
    """Remove only light background connected to image edges, preserving white clothes."""
    image = image.convert("RGBA")
    array = np.array(image)
    rgb = array[:, :, :3]
    possible_background = light_background_mask(rgb).astype(np.uint8)

    h, w = possible_background.shape
    flood_source = possible_background.copy()
    flood_mask = np.zeros((h + 2, w + 2), np.uint8)

    for x in range(w):
        if flood_source[0, x]:
            cv2.floodFill(flood_source, flood_mask, (x, 0), 2)
        if flood_source[h - 1, x]:
            cv2.floodFill(flood_source, flood_mask, (x, h - 1), 2)

    for y in range(h):
        if flood_source[y, 0]:
            cv2.floodFill(flood_source, flood_mask, (0, y), 2)
        if flood_source[y, w - 1]:
            cv2.floodFill(flood_source, flood_mask, (w - 1, y), 2)

    array[:, :, 3] = np.where(flood_source == 2, 0, array[:, :, 3])
    return Image.fromarray(array, "RGBA")


def extract_character_with_grabcut(image):
    """Extract foreground from a cropped candidate while preserving light clothing."""
    candidate = image.convert("RGB")
    rgb = np.array(candidate)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]

    mask = np.zeros((h, w), np.uint8)
    rect = (
        int(w * 0.06),
        int(h * 0.02),
        int(w * 0.88),
        int(h * 0.96),
    )
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(bgr, mask, rect, bgd_model, fgd_model, 9, cv2.GC_INIT_WITH_RECT)
        alpha = np.where(
            (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
            255,
            0,
        ).astype(np.uint8)
    except Exception:
        cleaned = remove_edge_connected_background(candidate)
        return cleaned

    kernel = np.ones((3, 3), np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel, iterations=2)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, kernel, iterations=1)

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(alpha, 8)
    if component_count > 1:
        largest = max(range(1, component_count), key=lambda idx: stats[idx, cv2.CC_STAT_AREA])
        alpha = np.where(labels == largest, 255, 0).astype(np.uint8)

    rgba = np.dstack([rgb, alpha])
    extracted = Image.fromarray(rgba, "RGBA")
    extracted = remove_edge_connected_background(extracted)
    bbox = extracted.getchannel("A").getbbox()
    return extracted.crop(bbox) if bbox else extracted


def place_on_transparent_canvas(sprite, size=(768, 1024)):
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    sprite = sprite.convert("RGBA")
    bbox = sprite.getchannel("A").getbbox()
    if bbox:
        sprite = sprite.crop(bbox)

    if sprite.width < 10 or sprite.height < 10:
        return canvas

    scale = min(size[0] * 0.70 / sprite.width, size[1] * 0.88 / sprite.height)
    new_size = (max(1, int(sprite.width * scale)), max(1, int(sprite.height * scale)))
    sprite = sprite.resize(new_size, Image.LANCZOS)

    x = (size[0] - sprite.width) // 2
    y = size[1] - sprite.height - 36
    canvas.alpha_composite(sprite, (x, y))
    return canvas


def build_sprite(raw_image):
    candidate = crop_best_center_character(raw_image)
    extracted = extract_character_with_grabcut(candidate)
    return place_on_transparent_canvas(extracted)


def sprite_quality_score(sprite):
    alpha = sprite.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return 0

    left, top, right, bottom = bbox
    width = right - left
    height = bottom - top
    area = np.count_nonzero(np.array(alpha) > 20)
    center_x = (left + right) / 2
    center_penalty = abs(center_x - sprite.width / 2)

    score = height * 3 + width + area / 450 - center_penalty
    if height < sprite.height * 0.60:
        score -= 900
    if top > sprite.height * 0.22:
        score -= 500
    if bottom < sprite.height * 0.78:
        score -= 500
    return score


def generate_raw_image(prompt, seed):
    generator = torch.Generator(device="cuda").manual_seed(seed)
    return pipe(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        num_inference_steps=30,
        guidance_scale=8.0,
        width=768,
        height=1024,
        generator=generator,
    ).images[0]


for character_index, item in enumerate(sprite_prompts):
    name = item["name"]
    base_name = safe_name(name)
    final_raw_path = SPRITE_DIR / f"{base_name}_full_body_raw.png"
    final_sprite_path = SPRITE_DIR / f"{base_name}_sprite.png"

    best = None
    print("Generating full-body sprite:", name)

    for attempt in range(1, MAX_ATTEMPTS_PER_CHARACTER + 1):
        seed = 1200 + character_index * 101 + attempt
        attempt_raw_path = SPRITE_DIR / f"{base_name}_attempt_{attempt}_raw.png"

        print("Attempt:", attempt, "seed:", seed)
        raw_image = generate_raw_image(item["prompt"], seed)
        raw_image.save(attempt_raw_path)

        sprite = build_sprite(raw_image)
        score = sprite_quality_score(sprite)
        print("Quality score:", round(score, 2))

        if best is None or score > best["score"]:
            best = {
                "score": score,
                "raw_image": raw_image,
                "sprite": sprite,
                "attempt_raw_path": attempt_raw_path,
            }

    best["raw_image"].save(final_raw_path)
    best["sprite"].save(final_sprite_path)

    item["raw_image_path"] = str(final_raw_path)
    item["sprite_path"] = str(final_sprite_path)
    item["quality_score"] = round(float(best["score"]), 2)

    print("Selected:", name, "score:", item["quality_score"])

print("Sprites generated")


def repair_existing_sprites_from_raw():
    for item in sprite_prompts:
        name = item["name"]
        base_name = safe_name(name)
        raw_path = SPRITE_DIR / f"{base_name}_full_body_raw.png"
        sprite_path = SPRITE_DIR / f"{base_name}_sprite.png"

        if not raw_path.exists():
            print("Missing raw image:", raw_path)
            continue

        print("Repairing sprite from raw:", name)
        raw_image = Image.open(raw_path).convert("RGBA")
        repaired = build_sprite(raw_image)
        repaired.save(sprite_path)

        item["raw_image_path"] = str(raw_path)
        item["sprite_path"] = str(sprite_path)
        item["quality_score"] = round(float(sprite_quality_score(repaired)), 2)


# %%
SPRITE_MANIFEST = SPRITE_DIR / "sprites_manifest.json"

with SPRITE_MANIFEST.open("w", encoding="utf-8") as file:
    json.dump(sprite_prompts, file, indent=2, ensure_ascii=False)

status = {
    "job_id": JOB_ID,
    "status": "module_4_sprites_completed",
    "step": "full_body_transparent_sprites_generated",
    "progress": 100,
    "sprites_manifest_path": str(SPRITE_MANIFEST),
}

with STATUS_JSON.open("w", encoding="utf-8") as file:
    json.dump(status, file, indent=2, ensure_ascii=False)

print("Saved sprite manifest:", SPRITE_MANIFEST)
print("Updated status:", STATUS_JSON)
