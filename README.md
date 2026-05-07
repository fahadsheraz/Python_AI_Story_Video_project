# AI Story Video Project

Local MVP for an AI story-to-video workflow.

Current modules:

1. User authentication placeholder
2. Story segmentation core engine
3. UI review and edit screen

Future modules:

4. Character generation
5. Background generation
6. Text-to-speech
7. Lip sync
8. Scene composition
9. Video rendering
10. Export
11. User management
12. Admin management

## Run Locally

Start the app:

```powershell
python -m app.server
```

Open:

```text
http://127.0.0.1:8000
```

## MVP Flow

1. Paste a story.
2. Click Segment Story.
3. Review scenes, characters, narration, and dialogues.
4. Edit anything that looks wrong.
5. Click Confirm Segmentation.

Confirmed data is saved in local SQLite at:

```text
data/app.db
```

## Colab Bridge Plan

After segmentation is confirmed, the project can create a job folder:

```text
Google Drive/
  AI_Story_Video_Project/
    jobs/
      job_001/
        input/
          segmentation.json
        output/
          characters/
          backgrounds/
          audio/
          video/
        status.json
```

Colab will read `segmentation.json`, generate assets, and write output files plus `status.json`.
