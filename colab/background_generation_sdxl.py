# AI Story Video Project - Colab Background Generation
#
# Run after Module 4 character images are complete.
# This notebook generates one background image per scene.


# %% [markdown]
# # Module 5: Background Generation
#
# This notebook reads `segmentation.json`, builds scene background prompts, and
# saves background images in:
#
# ```text
# output/backgrounds/
# ```


# %%
from google.colab import drive
drive.mount("/content/drive", force_remount=True)


# %%
!pip install -q diffusers transformers accelerate safetensors pillow


# %%
import json
import torch
from pathlib import Path
from diffusers import AutoPipelineForText2Image

JOB_ID = "job_0011"
PROJECT_ROOT = Path("/content/drive/MyDrive/AI_Story_Video_Project")
JOB_DIR = PROJECT_ROOT / "jobs" / JOB_ID
INPUT_JSON = JOB_DIR / "input" / "segmentation.json"
BACKGROUND_DIR = JOB_DIR / "output" / "backgrounds"
STATUS_JSON = JOB_DIR / "status.json"

BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)

print("CUDA available:", torch.cuda.is_available())
print("Input exists:", INPUT_JSON.exists())


# %%
with INPUT_JSON.open("r", encoding="utf-8") as file:
    segmentation = json.load(file)

print("Scenes:", len(segmentation.get("scenes", [])))


# %%
def build_background_prompt(scene):
    title = scene.get("title", "Scene")
    location = scene.get("location", "").strip()
    narration = scene.get("narration", "").strip()
    location_text = location if location else infer_location_from_text(narration)
    mood_text = infer_mood_from_text(narration)
    object_text = infer_key_objects_from_text(narration)

    return (
        f"Empty wide cinematic background environment for {title}. "
        f"Location: {location_text}. "
        f"Scene details: {narration}. "
        f"Mood: {mood_text}. "
        f"Important visible environment objects: {object_text}. "
        "Environment only. Absolutely no characters, no people, no humans, no silhouettes, no faces. "
        "No text, no logos. Clean animated film background art, detailed environment, "
        "wide establishing shot, 16:9 composition, empty foreground space for characters."
    )


def infer_location_from_text(text):
    lowered = text.lower()
    location_keywords = [
        "library",
        "room",
        "forest",
        "castle",
        "village",
        "city",
        "street",
        "school",
        "house",
        "office",
        "market",
        "mountain",
        "river",
        "beach",
        "spaceship",
        "cave",
        "garden",
        "hospital",
        "train",
        "station",
    ]

    for keyword in location_keywords:
        if keyword in lowered:
            return keyword

    return "story environment based on the scene details"


def infer_mood_from_text(text):
    lowered = text.lower()
    if any(word in lowered for word in ["night", "dark", "secret", "hidden", "mysterious", "whispered"]):
        return "mysterious and cinematic"
    if any(word in lowered for word in ["danger", "fear", "storm", "ran", "screamed"]):
        return "tense and dramatic"
    if any(word in lowered for word in ["morning", "sun", "happy", "beautiful"]):
        return "warm and hopeful"
    return "cinematic story mood"


def infer_key_objects_from_text(text):
    lowered = text.lower()
    object_keywords = [
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
        "computer",
        "phone",
    ]
    found = [keyword for keyword in object_keywords if keyword in lowered]
    return ", ".join(found[:6]) if found else "objects mentioned or implied by the scene"


background_prompts = []

for scene in segmentation.get("scenes", []):
    scene_number = scene.get("scene_number")
    background_prompts.append({
        "scene_id": scene.get("id"),
        "scene_number": scene_number,
        "title": scene.get("title"),
        "prompt": build_background_prompt(scene),
        "image_status": "pending",
        "image_path": None,
    })

print(json.dumps(background_prompts, indent=2, ensure_ascii=False))


# %%
MODEL_ID = "stabilityai/sdxl-turbo"

pipe = AutoPipelineForText2Image.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    variant="fp16",
)
pipe = pipe.to("cuda")

print("Model loaded")


# %%
NEGATIVE_PROMPT = (
    "people, person, human, man, woman, child, character, silhouette, face, body, "
    "portrait, selfie, crowd, text, logo, watermark, blurry, low quality, "
    "distorted architecture, duplicate objects, outdoor street, alley, city street"
)

generated_backgrounds = []

for item in background_prompts:
    scene_number = item["scene_number"]
    output_path = BACKGROUND_DIR / f"scene_{scene_number:02d}_background.png"

    print("Generating background for scene:", scene_number)
    image = pipe(
        prompt=item["prompt"],
        negative_prompt=NEGATIVE_PROMPT,
        num_inference_steps=4,
        guidance_scale=0.0,
        width=1024,
        height=576,
    ).images[0]

    image.save(output_path)

    item["image_status"] = "generated"
    item["image_path"] = str(output_path)
    generated_backgrounds.append(item)

print("Generated backgrounds:")
for item in generated_backgrounds:
    print(item["title"], "->", item["image_path"])


# %%
PROMPTS_JSON = BACKGROUND_DIR / "background_prompts.json"
MANIFEST_JSON = BACKGROUND_DIR / "backgrounds_manifest.json"

with PROMPTS_JSON.open("w", encoding="utf-8") as file:
    json.dump(background_prompts, file, indent=2, ensure_ascii=False)

with MANIFEST_JSON.open("w", encoding="utf-8") as file:
    json.dump(generated_backgrounds, file, indent=2, ensure_ascii=False)

status = {
    "job_id": JOB_ID,
    "status": "module_5_completed",
    "step": "background_images_generated",
    "progress": 100,
    "backgrounds_manifest_path": str(MANIFEST_JSON),
}

with STATUS_JSON.open("w", encoding="utf-8") as file:
    json.dump(status, file, indent=2, ensure_ascii=False)

print("Saved prompts:", PROMPTS_JSON)
print("Saved manifest:", MANIFEST_JSON)
print("Updated status:", STATUS_JSON)
