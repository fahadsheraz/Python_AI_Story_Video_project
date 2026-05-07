# AI Story Video Project - Colab Character Generation Starter
#
# Use this file in Google Colab:
# 1. Open https://colab.research.google.com
# 2. Create a new notebook
# 3. Copy each section below into notebook cells
# 4. Change JOB_ID if needed


# %% [markdown]
# # AI Story Video Project
# ## Module 4: Character Generation Starter
#
# This notebook reads a confirmed segmentation job from Google Drive and creates
# character generation prompts. In the next step, an image generation model can
# use these prompts to create character avatars.


# %%
from google.colab import drive
drive.mount("/content/drive")


# %%
import json
from pathlib import Path

JOB_ID = "job_0011"
PROJECT_ROOT = Path("/content/drive/MyDrive/AI_Story_Video_Project")
JOB_DIR = PROJECT_ROOT / "jobs" / JOB_ID
INPUT_JSON = JOB_DIR / "input" / "segmentation.json"
OUTPUT_DIR = JOB_DIR / "output"
CHARACTER_DIR = OUTPUT_DIR / "characters"
STATUS_JSON = JOB_DIR / "status.json"

CHARACTER_DIR.mkdir(parents=True, exist_ok=True)

print("Job folder:", JOB_DIR)
print("Input exists:", INPUT_JSON.exists())


# %%
with INPUT_JSON.open("r", encoding="utf-8") as file:
    segmentation = json.load(file)

print("Story title:", segmentation.get("title"))
print("Characters:", [character["name"] for character in segmentation.get("characters", [])])
print("Scenes:", len(segmentation.get("scenes", [])))


# %%
def build_character_prompt(character, segmentation):
    name = character.get("name", "Unknown")
    role = character.get("role", "Story character")
    description = character.get("description", "").strip()

    prompt_parts = [
        f"Single character portrait of {name}.",
        f"Role: {role}.",
        "Only one person in the image.",
        "Plain light gray studio background.",
        "No room, no library, no furniture, no books, no scene environment.",
    ]

    if description:
        prompt_parts.append(f"Character description: {description}.")

    prompt_parts.extend([
        "Style: clean 3D animated film character avatar, expressive face, polished design.",
        "Framing: centered upper body portrait, character facing camera.",
        "Keep the design consistent for later scene-wise regeneration.",
    ])

    return " ".join(prompt_parts)


character_prompts = []

for character in segmentation.get("characters", []):
    prompt = build_character_prompt(character, segmentation)
    item = {
        "character_id": character.get("id"),
        "name": character.get("name"),
        "prompt": prompt,
        "image_status": "pending",
        "image_path": None,
    }
    character_prompts.append(item)

print(json.dumps(character_prompts, indent=2, ensure_ascii=False))


# %%
PROMPTS_JSON = CHARACTER_DIR / "character_prompts.json"

with PROMPTS_JSON.open("w", encoding="utf-8") as file:
    json.dump(character_prompts, file, indent=2, ensure_ascii=False)

status = {
    "job_id": JOB_ID,
    "status": "module_4_started",
    "step": "character_prompts_created",
    "progress": 20,
    "character_prompts_path": str(PROMPTS_JSON),
}

with STATUS_JSON.open("w", encoding="utf-8") as file:
    json.dump(status, file, indent=2, ensure_ascii=False)

print("Saved:", PROMPTS_JSON)
print("Updated:", STATUS_JSON)


# %% [markdown]
# ## Next Step
#
# After this cell runs successfully, the Drive job folder should contain:
#
# ```text
# output/characters/character_prompts.json
# status.json
# ```
#
# The next notebook version will use these prompts to generate actual character
# images and save them in `output/characters/`.
