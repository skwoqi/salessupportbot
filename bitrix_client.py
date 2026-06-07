from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any


class BitrixClient:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = self._normalize_webhook_url(webhook_url)

    @staticmethod
    def _normalize_webhook_url(webhook_url: str) -> str:
        cleaned = (webhook_url or "").strip().rstrip("/")
        # Accept both base webhook URL and service URLs like .../profile.json.
        if cleaned.endswith(".json"):
            cleaned = cleaned.rsplit("/", 1)[0]
        return cleaned

    def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.webhook_url:
            return {"result": None, "error": "BITRIX_WEBHOOK_URL is empty"}

        url = f"{self.webhook_url}/{method}.json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        retries = 3
        last_error = ""
        for attempt in range(1, retries + 1):
            req = urllib.request.Request(
                url=url,
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raw = ""
                try:
                    raw = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    raw = str(exc)
                return {
                    "result": None,
                    "error": f"http_{exc.code}",
                    "error_description": raw,
                }
            except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
                last_error = str(exc)
                if attempt < retries:
                    time.sleep(1.5 * attempt)
                    continue
                return {
                    "result": None,
                    "error": f"request_failed_after_{retries}_attempts: {last_error}",
                }
        return {"result": None, "error": "unknown_request_error"}

    def create_lead(self, title: str, fields: dict[str, Any], comments: str) -> tuple[bool, str]:
        payload = {
            "fields": {
                "TITLE": title,
                "COMMENTS": comments,
                **fields,
            },
        }
        result = self._post("crm.lead.add", payload)
        if result.get("error"):
            error = str(result.get("error", ""))
            error_desc = str(result.get("error_description", ""))

            # Some portals reject SOURCE_ID when the dictionary is custom or disabled.
            if "SOURCE_ID" in payload["fields"] and (
                "SOURCE_ID" in error_desc or "SOURCE_ID" in error
            ):
                fields_without_source = dict(payload["fields"])
                fields_without_source.pop("SOURCE_ID", None)
                retry_payload = {"fields": fields_without_source}
                retry_result = self._post("crm.lead.add", retry_payload)
                if retry_result.get("error"):
                    retry_err = str(retry_result.get("error", ""))
                    retry_desc = str(retry_result.get("error_description", ""))
                    return False, f"{retry_err}: {retry_desc}".strip(": ")
                return True, str(retry_result.get("result", ""))

            return False, f"{error}: {error_desc}".strip(": ")
        return True, str(result.get("result", ""))
