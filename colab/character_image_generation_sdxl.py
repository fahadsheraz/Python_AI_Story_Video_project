# AI Story Video Project - Colab Character Image Generation
#
# Run after `character_generation_starter.py`.
# This notebook uses Stable Diffusion through Hugging Face Diffusers.


# %% [markdown]
# # Module 4: Generate Character Images
#
# Before running:
#
# 1. Colab menu: Runtime -> Change runtime type
# 2. Hardware accelerator: GPU
# 3. Runtime -> Run all


# %%
from google.colab import drive
drive.mount("/content/drive")


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
CHARACTER_DIR = JOB_DIR / "output" / "characters"
PROMPTS_JSON = CHARACTER_DIR / "character_prompts.json"
STATUS_JSON = JOB_DIR / "status.json"

print("CUDA available:", torch.cuda.is_available())
print("Prompts exist:", PROMPTS_JSON.exists())


# %%
with PROMPTS_JSON.open("r", encoding="utf-8") as file:
    character_prompts = json.load(file)

print("Characters to generate:", [item["name"] for item in character_prompts])


# %%
MODEL_ID = "stabilityai/sdxl-turbo"

pipe = AutoPipelineForText2Image.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    variant="fp16",
)
pipe = pipe.to("cuda")


# %%
NEGATIVE_PROMPT = (
    "low quality, blurry, distorted face, extra fingers, extra limbs, "
    "bad anatomy, watermark, text, logo, cropped head, duplicate character, "
    "multiple people, second person, group, library, room, books, furniture, "
    "desk, background scene, full environment"
)

generated = []

for item in character_prompts:
    name = item["name"]
    prompt = item["prompt"]
    output_path = CHARACTER_DIR / f"{name.lower().replace(' ', '_')}.png"

    print("Generating:", name)
    image = pipe(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        num_inference_steps=4,
        guidance_scale=0.0,
        width=768,
        height=768,
    ).images[0]

    image.save(output_path)

    item["image_status"] = "generated"
    item["image_path"] = str(output_path)
    generated.append({
        "name": name,
        "image_path": str(output_path),
        "prompt": prompt,
    })

print("Generated images:", generated)


# %%
MANIFEST_JSON = CHARACTER_DIR / "characters_manifest.json"

with PROMPTS_JSON.open("w", encoding="utf-8") as file:
    json.dump(character_prompts, file, indent=2, ensure_ascii=False)

with MANIFEST_JSON.open("w", encoding="utf-8") as file:
    json.dump(generated, file, indent=2, ensure_ascii=False)

status = {
    "job_id": JOB_ID,
    "status": "module_4_completed",
    "step": "character_images_generated",
    "progress": 100,
    "characters_manifest_path": str(MANIFEST_JSON),
}

with STATUS_JSON.open("w", encoding="utf-8") as file:
    json.dump(status, file, indent=2, ensure_ascii=False)

print("Saved manifest:", MANIFEST_JSON)
print("Updated status:", STATUS_JSON)


# %% [markdown]
# Expected files:
#
# ```text
# output/characters/sara.png
# output/characters/ali.png
# output/characters/characters_manifest.json
# output/characters/character_prompts.json
# status.json
# ```
