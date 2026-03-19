#!/usr/bin/env python3
import json
import os
import re
import sys
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import build_opener, Request

HOST = "127.0.0.1"
PORT = 8787
TIMEOUT_SECONDS = 30
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
OPENER = build_opener()

def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def _request_json(url: str, headers: dict | None = None) -> dict:
    request = Request(url, headers=headers or {}, method="GET")
    with OPENER.open(request, timeout=TIMEOUT_SECONDS) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))

def brave_search(query: str, count: int = 5) -> dict:
    if not BRAVE_API_KEY:
        return {"ok": False, "error": "missing_brave_api_key"}
    url = "https://api.search.brave.com/res/v1/web/search" + f"?q={quote(query)}&count={count}"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
        "User-Agent": "openclaw-search-bridge/0.1",
    }
    try:
        data = _request_json(url, headers=headers)
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return {"ok": False, "error": "http_error", "status": e.code, "body": body}
    except URLError as e:
        return {"ok": False, "error": "url_error", "reason": str(e.reason)}
    except Exception as e:
        return {"ok": False, "error": "decode_error", "reason": str(e)}
    results = []
    for item in data.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
            "age": item.get("age", ""),
        })
    return {"ok": True, "query": query, "count": count, "results": results}

def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p\s*>", "\n\n", html)
    html = re.sub(r"(?i)</div\s*>", "\n", html)
    html = re.sub(r"(?i)</li\s*>", "\n", html)
    html = re.sub(r"(?is)<.*?>", " ", html)
    text = unescape(html)
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()

def fetch_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"ok": False, "error": "invalid_url"}
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 openclaw-search-bridge/0.1"}, method="GET")
    try:
        with OPENER.open(request, timeout=TIMEOUT_SECONDS) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return {"ok": False, "error": "http_error", "status": e.code, "body": body}
    except URLError as e:
        return {"ok": False, "error": "url_error", "reason": str(e.reason)}
    except Exception as e:
        return {"ok": False, "error": "fetch_error", "reason": str(e)}
    text = raw.decode("utf-8", errors="replace")
    if "html" in content_type.lower():
        text = _strip_html(text)
    return {"ok": True, "url": url, "text": text[:200000]}

class SearchBridgeHandler(BaseHTTPRequestHandler):
    server_version = "SearchBridge/0.1"
    def do_GET(self):
        if self.path == "/health":
            return _json_response(self, 200, {
                "ok": True,
                "service": "search-bridge",
                "host": HOST,
                "port": PORT,
                "has_brave_key": bool(BRAVE_API_KEY),
                "http_proxy": bool(os.environ.get("HTTP_PROXY")),
                "https_proxy": bool(os.environ.get("HTTPS_PROXY")),
            })
        _json_response(self, 404, {"ok": False, "error": "not_found"})
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            return _json_response(self, 400, {"ok": False, "error": "invalid_json"})
        if self.path == "/search":
            query = body.get("query", "").strip()
            count = int(body.get("count", 5) or 5)
            if not query:
                return _json_response(self, 400, {"ok": False, "error": "missing_query"})
            payload = brave_search(query, count)
            return _json_response(self, 200 if payload.get("ok") else 500, payload)
        if self.path == "/fetch":
            url = body.get("url", "").strip()
            if not url:
                return _json_response(self, 400, {"ok": False, "error": "missing_url"})
            payload = fetch_url(url)
            return _json_response(self, 200 if payload.get("ok") else 500, payload)
        _json_response(self, 404, {"ok": False, "error": "not_found"})
    def log_message(self, fmt: str, *args):
        sys.stdout.write("[search-bridge] " + (fmt % args) + "\n")
        sys.stdout.flush()

def main():
    server = ThreadingHTTPServer((HOST, PORT), SearchBridgeHandler)
    print(f"Search Bridge listening on http://{HOST}:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    main()
