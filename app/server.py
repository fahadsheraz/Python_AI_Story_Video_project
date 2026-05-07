from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.segmentation import segment_story
from app.storage import create_colab_job, create_project, get_project, init_db, list_projects, update_segmentation

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"


class StoryVideoHandler(BaseHTTPRequestHandler):
    server_version = "StoryVideoMVP/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/":
            self._send_file(STATIC_DIR / "index.html")
            return

        if path.startswith("/static/"):
            self._send_file(STATIC_DIR / path.removeprefix("/static/"))
            return

        if path == "/api/projects":
            self._send_json(list_projects())
            return

        if path.startswith("/api/projects/"):
            project = self._find_project(path)
            if project is None:
                return
            self._send_json(project)
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Page not found.")

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/projects/segment":
            payload = self._read_json()
            story = str(payload.get("story", "")).strip()
            title = str(payload.get("title", "Untitled Story")).strip() or "Untitled Story"
            if not story:
                self._send_error(HTTPStatus.BAD_REQUEST, "Story text is required.")
                return

            segmentation = segment_story(title, story)
            project_id = create_project(segmentation["title"], story, segmentation)
            self._send_json({"project_id": project_id, "segmentation": segmentation}, HTTPStatus.CREATED)
            return

        if path.startswith("/api/projects/") and path.endswith("/confirm"):
            project_id = _parse_project_id(path)
            if project_id is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return

            existing = get_project(project_id)
            if existing is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            if existing["locked"]:
                self._send_json(existing)
                return

            segmentation = self._read_json()
            segmentation["status"] = "confirmed"
            update_segmentation(project_id, segmentation, locked=True)
            self._send_json(get_project(project_id))
            return

        if path.startswith("/api/projects/") and path.endswith("/colab-job"):
            project_id = _parse_project_id(path)
            if project_id is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return

            project = get_project(project_id)
            if project is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            if not project["locked"]:
                self._send_error(HTTPStatus.CONFLICT, "Confirm segmentation before creating a Colab job.")
                return

            job = create_colab_job(project_id)
            if job is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return

            self._send_json(job, HTTPStatus.CREATED)
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")

    def do_PUT(self) -> None:
        path = urlparse(self.path).path

        if path.startswith("/api/projects/") and path.endswith("/segmentation"):
            project_id = _parse_project_id(path)
            if project_id is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return

            existing = get_project(project_id)
            if existing is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            if existing["locked"]:
                self._send_error(HTTPStatus.CONFLICT, "Segmentation is already confirmed and locked.")
                return

            segmentation = self._read_json()
            segmentation["status"] = "draft"
            update_segmentation(project_id, segmentation, locked=False)
            self._send_json(get_project(project_id))
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _find_project(self, path: str) -> dict | None:
        project_id = _parse_project_id(path)
        if project_id is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return None

        project = get_project(project_id)
        if project is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return None

        return project

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            data = json.loads(raw_body.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _send_json(self, data: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path) -> None:
        resolved = file_path.resolve()
        static_root = STATIC_DIR.resolve()
        if not str(resolved).startswith(str(static_root)) or not resolved.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "File not found.")
            return

        body = resolved.read_bytes()
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"detail": message}, status)


def _parse_project_id(path: str) -> int | None:
    parts = [part for part in path.split("/") if part]
    try:
        project_index = parts.index("projects")
        return int(parts[project_index + 1])
    except (ValueError, IndexError):
        return None


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    init_db()
    server = ThreadingHTTPServer((host, port), StoryVideoHandler)
    print(f"AI Story Video Project running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
