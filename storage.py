from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class UserContext:
    user_id: int
    state: str
    payload: dict[str, Any]


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    phone TEXT,
                    email TEXT,
                    state TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    request_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_user_context(self, user_id: int, default_state: str) -> UserContext:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT user_id, state, payload_json FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                self.upsert_user(
                    user_id=user_id,
                    state=default_state,
                    payload={},
                )
                return UserContext(user_id=user_id, state=default_state, payload={})
            return UserContext(
                user_id=row["user_id"],
                state=row["state"],
                payload=json.loads(row["payload_json"] or "{}"),
            )

    def upsert_user(
        self,
        user_id: int,
        state: str,
        payload: dict[str, Any],
        username: str | None = None,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO users (
                    user_id, username, full_name, phone, email, state, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = COALESCE(excluded.username, users.username),
                    full_name = COALESCE(excluded.full_name, users.full_name),
                    phone = COALESCE(excluded.phone, users.phone),
                    email = COALESCE(excluded.email, users.email),
                    state = excluded.state,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    username,
                    full_name,
                    phone,
                    email,
                    state,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()

    def create_request(
        self,
        user_id: int,
        request_type: str,
        title: str,
        details: dict[str, Any],
        status: str = "NEW",
    ) -> int:
        with closing(self._connect()) as conn:
            cur = conn.execute(
                """
                INSERT INTO requests (
                    user_id, request_type, status, title, details_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    request_type,
                    status,
                    title,
                    json.dumps(details, ensure_ascii=False),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def set_request_status(self, request_id: int, status: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE requests SET status = ? WHERE id = ?",
                (status, request_id),
            )
            conn.commit()
