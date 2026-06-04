from __future__ import annotations

from collections.abc import Iterable
import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jokerag_agent.dashboard_service import DashboardService


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class DashboardHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type[BaseHTTPRequestHandler],
        service: DashboardService,
    ) -> None:
        super().__init__(server_address, RequestHandlerClass)
        self.service = service


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server: DashboardHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        path = self._normalized_path()
        if path == "/api/health":
            self._send_json({"ok": True})
            return
        if path == "/api/dashboard":
            try:
                payload = self.server.service.current_dashboard()
            except Exception as error:  # pragma: no cover - exercised in manual runs
                self._send_json(
                    {"ok": False, "error": str(error)},
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )
                return
            self._send_json(payload)
            return
        if path == "/":
            self._send_static_file(REPO_ROOT / "dashboard.html")
            return
        self._send_static_file(REPO_ROOT / path.lstrip("/"))

    def do_POST(self) -> None:  # noqa: N802
        path = self._normalized_path()
        if path == "/api/refresh":
            try:
                payload = self.server.service.refresh_daily_run(force=True)
            except Exception as error:  # pragma: no cover - exercised in manual runs
                self._send_json(
                    {"ok": False, "error": str(error)},
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )
                return
            self._send_json(payload)
            return

        if path == "/api/votes":
            body = self._read_json_body()
            if body is None:
                self._send_json(
                    {"ok": False, "error": "Expected JSON body."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            try:
                joke_id = str(body["jokeId"])
                voter_id = str(body["voterId"])
                rating = int(body["rating"])
                payload = self.server.service.record_vote(joke_id, voter_id, rating)
            except (KeyError, TypeError, ValueError) as error:
                self._send_json(
                    {"ok": False, "error": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            except Exception as error:  # pragma: no cover - exercised in manual runs
                self._send_json(
                    {"ok": False, "error": str(error)},
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )
                return
            self._send_json(payload)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if content_length <= 0:
            return None

        payload = self.rfile.read(content_length)
        try:
            data = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _normalized_path(self) -> str:
        path = urlparse(self.path).path
        return path or "/"

    def _send_json(
        self,
        payload: object,
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static_file(self, path: Path) -> None:
        if path.is_dir():
            path = path / "dashboard.html"
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_service() -> DashboardService:
    database_url = REPO_ROOT / "data" / "app.db"
    return DashboardService(database_url=database_url)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the JokerAg dashboard.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    args = parser.parse_args(list(argv) if argv is not None else None)

    service = build_service()
    server = DashboardHTTPServer((args.host, args.port), DashboardRequestHandler, service)
    print(f"Serving dashboard on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
