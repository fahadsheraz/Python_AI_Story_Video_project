# Full Process V2

This is the recommended fresh process after the MVP improvements.

## Local App

1. Open the local app:

```text
http://127.0.0.1:8000
```

2. Paste story.
3. Click `Segment Story`.
4. Review scenes, characters, dialogues, layout, and descriptions.
5. Click `Save Draft`.
6. Click `Confirm Segmentation`.
7. Click `Prepare Colab Job`.
8. Upload the generated job folder to:

```text
My Drive/AI_Story_Video_Project/jobs/
```

## Colab Order

Run notebooks/scripts in this order:

1. `full_body_character_sprites.py`
2. `background_generation_sdxl.py`
3. `tts_generation_edge.py`
4. `lip_sync_prep.py`
5. `video_composition_simple.py`

## Current Lip Sync Status

`lip_sync_prep.py` creates mouth timing JSON from dialogue audio.
It does not yet render real mouth animation. The next production upgrade can
plug in Wav2Lip, SadTalker, LivePortrait, or another face animation model.

## Output

Final video path:

```text
output/video/final_animatic.mp4
```
