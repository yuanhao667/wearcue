import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from .image_service import ImageService


AI_USAGE_LIMITS = {"vision": 30, "swap": 4, "advice": 4}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid4().hex[:12])


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def user_local_date(tz_name: Optional[str]) -> str:
    try:
        tz = ZoneInfo(tz_name or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).strftime("%Y-%m-%d")


class Store:
    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = data_dir or Path(os.getenv("DATA_DIR", Path.cwd() / "data"))
        self.upload_dir = self.data_dir / "uploads"
        self.generated_dir = self.data_dir / "generated"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "outfit-signal.sqlite3"
        self._init()
        self._seed_existing_user_examples()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _add_column(db: sqlite3.Connection, table: str, definition: str) -> None:
        column = definition.split()[0]
        columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

    def _init(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1), city_id TEXT NOT NULL,
                    city_name TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL,
                    timezone TEXT NOT NULL, audience TEXT NOT NULL, cold_offset INTEGER NOT NULL,
                    reminder_enabled INTEGER NOT NULL, reminder_time TEXT NOT NULL,
                    reminder_days TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inspirations (
                    id TEXT PRIMARY KEY, upload_key TEXT NOT NULL UNIQUE,
                    content_hash TEXT NOT NULL, original_name TEXT NOT NULL,
                    media_type TEXT NOT NULL, file_path TEXT NOT NULL, status TEXT NOT NULL,
                    provider TEXT NOT NULL, result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outfits (
                    id TEXT PRIMARY KEY, label TEXT NOT NULL, audience TEXT NOT NULL,
                    source TEXT NOT NULL, components_json TEXT NOT NULL,
                    scene_ids_json TEXT NOT NULL, suitable_min REAL NOT NULL,
                    suitable_max REAL NOT NULL, favorite INTEGER NOT NULL,
                    in_pool INTEGER NOT NULL, inspiration_id TEXT,
                    skip_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, replication_json TEXT NOT NULL DEFAULT '{}',
                    analysis_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id TEXT PRIMARY KEY, endpoint TEXT NOT NULL UNIQUE, p256dh TEXT NOT NULL,
                    auth TEXT NOT NULL, enabled INTEGER NOT NULL, last_result TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY, week_key TEXT NOT NULL UNIQUE, choice TEXT NOT NULL,
                    old_offset INTEGER NOT NULL, new_offset INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS skip_events (
                    outfit_id TEXT NOT NULL, local_date TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (outfit_id, local_date)
                );
                CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, invite_code_hash TEXT NOT NULL UNIQUE,
                    nickname TEXT NOT NULL, audience TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY, city_id TEXT NOT NULL, city_name TEXT NOT NULL,
                    latitude REAL NOT NULL, longitude REAL NOT NULL, timezone TEXT NOT NULL,
                    audience TEXT NOT NULL, cold_offset INTEGER NOT NULL,
                    reminder_enabled INTEGER NOT NULL, reminder_time TEXT NOT NULL,
                    reminder_days TEXT NOT NULL, updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS outfit_states (
                    user_id TEXT NOT NULL, outfit_id TEXT NOT NULL, favorite INTEGER,
                    in_pool INTEGER, scene_ids_json TEXT, skip_count INTEGER NOT NULL DEFAULT 0,
                    hidden INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, outfit_id)
                );
                CREATE TABLE IF NOT EXISTS user_skip_events (
                    user_id TEXT NOT NULL, outfit_id TEXT NOT NULL, local_date TEXT NOT NULL,
                    created_at TEXT NOT NULL, PRIMARY KEY(user_id, outfit_id, local_date)
                );
                CREATE TABLE IF NOT EXISTS analysis_events (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    local_date TEXT NOT NULL, usage_type TEXT NOT NULL DEFAULT 'vision',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_advice_cache (
                    user_id TEXT NOT NULL, recommendation_id TEXT NOT NULL,
                    result_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, recommendation_id)
                );
                CREATE TABLE IF NOT EXISTS ai_outfit_image_cache (
                    user_id TEXT NOT NULL, recommendation_id TEXT NOT NULL,
                    file_path TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, recommendation_id)
                );
                """
            )
            self._add_column(db, "outfits", "replication_json TEXT NOT NULL DEFAULT '{}'")
            self._add_column(db, "outfits", "analysis_json TEXT NOT NULL DEFAULT '{}'")
            self._add_column(db, "outfits", "owner_user_id TEXT")
            self._add_column(db, "inspirations", "owner_user_id TEXT")
            for table in ("settings", "user_settings"):
                self._add_column(db, table, "height_group TEXT NOT NULL DEFAULT '中等'")
                self._add_column(db, table, "weight_group TEXT NOT NULL DEFAULT '中等'")
                self._add_column(db, table, "age_group TEXT NOT NULL DEFAULT '青年'")
            for table in ("push_subscriptions", "notification_deliveries", "feedback"):
                self._add_column(db, table, "user_id TEXT")
            self._add_column(db, "analysis_events", "usage_type TEXT NOT NULL DEFAULT 'vision'")
            db.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
                CREATE INDEX IF NOT EXISTS idx_outfits_owner ON outfits(owner_user_id);
                CREATE INDEX IF NOT EXISTS idx_inspirations_owner ON inspirations(owner_user_id);
                CREATE INDEX IF NOT EXISTS idx_analysis_events_user_date ON analysis_events(user_id, local_date);
                CREATE INDEX IF NOT EXISTS idx_analysis_events_quota
                ON analysis_events(user_id, local_date, usage_type);
                """
            )
            db.execute(
                """INSERT OR IGNORE INTO settings
                (id,city_id,city_name,latitude,longitude,timezone,audience,cold_offset,
                 reminder_enabled,reminder_time,reminder_days,updated_at)
                VALUES (1,'1816670','北京',39.9042,116.4074,'Asia/Shanghai','mens',0,1,
                        '07:30','[1,2,3,4,5]',?)""",
                (_now(),),
            )

    def _seed_existing_user_examples(self) -> None:
        with self.connect() as db:
            users = db.execute("SELECT user_id,audience FROM user_settings").fetchall()
        for user in users:
            self._ensure_user_example(user["user_id"], user["audience"])

    def _ensure_user_example(self, user_id: str, audience: str) -> None:
        version_key = f"default_example_v1:{user_id}:{audience}"
        with self.connect() as db:
            if db.execute("SELECT 1 FROM app_meta WHERE key=?", (version_key,)).fetchone():
                return
        defaults_dir = Path(__file__).resolve().parents[1] / "defaults"
        manifest = json.loads((defaults_dir / "outfits.json").read_text(encoding="utf-8"))
        entry = next(item for item in manifest["examples"] if item["audience"] == audience)
        image_data = (defaults_dir / "images" / entry["image"]).read_bytes()
        digest = hashlib.sha256(image_data).hexdigest()
        paths = ImageService(self.upload_dir).process_and_store(image_data, digest)
        upload_key = f"system-ai-example-v1-{audience}"
        inspiration = self.get_inspiration_by_key(upload_key, user_id)
        outfit = entry["outfit"]
        if not inspiration:
            result = {
                "model_version": "WearCue-System-Example-v1",
                "garment_audience": audience,
                "requires_user_confirmation": False,
                "suggested_scenes": outfit["scene_ids"],
                "suggested_temperature": {"min": outfit["suitable_min"], "max": outfit["suitable_max"]},
                "suggested_season": "winter" if outfit["suitable_max"] <= 12 else "summer",
                "components": outfit["components"],
                "replication_guide": outfit["replication_guide"],
                "outfit_analysis": outfit["outfit_analysis"],
            }
            inspiration = self.create_inspiration(
                {
                    "upload_key": upload_key,
                    "content_hash": digest,
                    "original_name": entry["image"],
                    "media_type": "image/jpeg",
                    "file_path": paths["original"],
                    "status": "ready",
                    "provider": "system-ai-example",
                    "result_json": json.dumps(result, ensure_ascii=False),
                },
                user_id,
            )
        outfit_id = f"example_{audience}_{_hash(user_id)[:12]}"
        if not self.get_outfit(outfit_id, user_id):
            self.save_outfit(
                outfit | {"audience": audience, "source": "system", "inspiration_id": inspiration["id"]},
                outfit_id,
                user_id,
            )
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO app_meta VALUES (?,?)", (version_key, "1"))

    @staticmethod
    def _settings(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        result.pop("user_id", None)
        result["reminder_enabled"] = bool(result["reminder_enabled"])
        result["reminder_days"] = json.loads(result["reminder_days"])
        return result

    @staticmethod
    def _user(row: sqlite3.Row) -> Dict[str, Any]:
        return {"id": row["id"], "nickname": row["nickname"], "audience": row["audience"]}

    def _create_user_settings(
        self, db: sqlite3.Connection, user_id: str, audience: str, legacy: bool
    ) -> None:
        if legacy:
            source = dict(db.execute("SELECT * FROM settings WHERE id=1").fetchone())
        else:
            source = {
                "city_id": "1816670", "city_name": "北京", "latitude": 39.9042,
                "longitude": 116.4074, "timezone": "Asia/Shanghai", "cold_offset": 0,
                "reminder_enabled": 1, "reminder_time": "07:30",
                "reminder_days": "[1,2,3,4,5]", "height_group": "中等",
                "weight_group": "中等", "age_group": "青年",
            }
        db.execute(
            """INSERT INTO user_settings
            (user_id,city_id,city_name,latitude,longitude,timezone,audience,cold_offset,
             reminder_enabled,reminder_time,reminder_days,height_group,weight_group,age_group,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id, source["city_id"], source["city_name"], source["latitude"],
                source["longitude"], source["timezone"], audience, source["cold_offset"],
                source["reminder_enabled"], source["reminder_time"], source["reminder_days"],
                source["height_group"], source["weight_group"], source["age_group"], _now(),
            ),
        )

    def login(self, invite_code: str, nickname: str, audience: str) -> Dict[str, Any]:
        code_hash = _hash(invite_code)
        now = _now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            user = db.execute(
                "SELECT * FROM users WHERE invite_code_hash=?", (code_hash,)
            ).fetchone()
            if not user:
                user_id = _id("user")
                db.execute(
                    "INSERT INTO users VALUES (?,?,?,?,?,?)",
                    (user_id, code_hash, nickname[:5], audience, now, now),
                )
                claimed = db.execute(
                    "SELECT value FROM app_meta WHERE key='legacy_data_claimed'"
                ).fetchone()
                is_first_user = not claimed
                self._create_user_settings(db, user_id, audience, is_first_user)
                if is_first_user:
                    db.execute(
                        "UPDATE outfits SET owner_user_id=? WHERE owner_user_id IS NULL",
                        (user_id,),
                    )
                    db.execute(
                        "UPDATE inspirations SET owner_user_id=? WHERE owner_user_id IS NULL",
                        (user_id,),
                    )
                    for table in ("push_subscriptions", "notification_deliveries", "feedback"):
                        db.execute(f"UPDATE {table} SET user_id=? WHERE user_id IS NULL", (user_id,))
                    db.execute(
                        "INSERT INTO app_meta VALUES ('legacy_data_claimed',?)", (user_id,)
                    )
                user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?)",
                (_hash(token), user["id"], expires_at, now),
            )
        self._ensure_user_example(user["id"], user["audience"])
        return {"token": token, "expires_at": expires_at, "user": self._user(user)}

    def user_for_token(self, token: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute(
                """SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.expires_at>?""",
                (_hash(token), _now()),
            ).fetchone()
        return self._user(row) if row else None

    def logout(self, token: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(token),))

    def update_nickname(self, user_id: str, nickname: str) -> Dict[str, Any]:
        with self.connect() as db:
            db.execute(
                "UPDATE users SET nickname=?,updated_at=? WHERE id=?",
                (nickname[:5], _now(), user_id),
            )
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return self._user(row)

    def get_settings(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM user_settings WHERE user_id=?" if user_id
                else "SELECT * FROM settings WHERE id=1",
                (user_id,) if user_id else (),
            ).fetchone()
        return self._settings(row)

    def save_settings(
        self, payload: Dict[str, Any], user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        current = self.get_settings(user_id)
        current.update(payload)
        table = "user_settings" if user_id else "settings"
        where = "user_id=?" if user_id else "id=1"
        values: List[Any] = [
            current["city_id"], current["city_name"], current["latitude"],
            current["longitude"], current["timezone"], current["audience"],
            current["cold_offset"], current["height_group"], current["weight_group"],
            current["age_group"],
            int(current["reminder_enabled"]),
            current["reminder_time"], json.dumps(current["reminder_days"]), _now(),
        ]
        if user_id:
            values.append(user_id)
        with self.connect() as db:
            db.execute(
                f"""UPDATE {table} SET city_id=?,city_name=?,latitude=?,longitude=?,timezone=?,
                audience=?,cold_offset=?,height_group=?,weight_group=?,age_group=?,reminder_enabled=?,
                reminder_time=?,reminder_days=?,updated_at=?
                WHERE {where}""",
                values,
            )
            if user_id and "audience" in payload:
                db.execute(
                    "UPDATE users SET audience=?,updated_at=? WHERE id=?",
                    (current["audience"], _now(), user_id),
                )
        if user_id and "audience" in payload:
            self._ensure_user_example(user_id, current["audience"])
        return self.get_settings(user_id)

    def list_reminder_users(self) -> List[Dict[str, Any]]:
        """Return every user whose daily reminder is enabled."""
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM user_settings WHERE reminder_enabled=1"
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["reminder_enabled"] = bool(item["reminder_enabled"])
            item["reminder_days"] = json.loads(item["reminder_days"])
            result.append(item)
        return result

    @staticmethod
    def _outfit(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        result.pop("owner_user_id", None)
        result["components"] = json.loads(result.pop("components_json"))
        result["scene_ids"] = json.loads(result.pop("scene_ids_json"))
        result.pop("favorite", None)
        result["in_pool"] = bool(result["in_pool"])
        result["replication_guide"] = json.loads(result.pop("replication_json", "{}"))
        result["outfit_analysis"] = json.loads(result.pop("analysis_json", "{}"))
        return result

    def _apply_state(
        self, db: sqlite3.Connection, outfit: Dict[str, Any], user_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        if not user_id:
            return outfit
        state = db.execute(
            "SELECT * FROM outfit_states WHERE user_id=? AND outfit_id=?",
            (user_id, outfit["id"]),
        ).fetchone()
        if not state:
            return outfit
        if state["hidden"]:
            return None
        if state["in_pool"] is not None:
            outfit["in_pool"] = bool(state["in_pool"])
        if state["scene_ids_json"] is not None:
            outfit["scene_ids"] = json.loads(state["scene_ids_json"])
        outfit["skip_count"] = state["skip_count"]
        return outfit

    def list_outfits(
        self, in_pool: Optional[bool] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM outfits"
        values: List[Any] = []
        if user_id:
            query += " WHERE owner_user_id=?"
            values.append(user_id)
        query += " ORDER BY updated_at DESC"
        with self.connect() as db:
            result = []
            for row in db.execute(query, values):
                outfit = self._apply_state(db, self._outfit(row), user_id)
                if not outfit:
                    continue
                if in_pool is not None and outfit["in_pool"] != in_pool:
                    continue
                result.append(outfit)
            return result

    def get_outfit(
        self, outfit_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM outfits WHERE id=? AND owner_user_id=?"
                if user_id else "SELECT * FROM outfits WHERE id=?",
                (outfit_id, user_id) if user_id else (outfit_id,),
            ).fetchone()
            return self._apply_state(db, self._outfit(row), user_id) if row else None

    def get_outfit_by_inspiration(
        self, inspiration_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM outfits WHERE inspiration_id=?"
        values: List[Any] = [inspiration_id]
        if user_id:
            query += " AND owner_user_id=?"
            values.append(user_id)
        query += " ORDER BY updated_at DESC LIMIT 1"
        with self.connect() as db:
            row = db.execute(query, values).fetchone()
            return self._apply_state(db, self._outfit(row), user_id) if row else None

    @staticmethod
    def _upsert_state(
        db: sqlite3.Connection, user_id: str, outfit_id: str, changes: Dict[str, Any]
    ) -> None:
        existing = db.execute(
            "SELECT * FROM outfit_states WHERE user_id=? AND outfit_id=?", (user_id, outfit_id)
        ).fetchone()
        state = dict(existing) if existing else {
            "user_id": user_id, "outfit_id": outfit_id, "favorite": None,
            "in_pool": None, "scene_ids_json": None, "skip_count": 0, "hidden": 0,
        }
        state.update(changes)
        state["updated_at"] = _now()
        db.execute(
            """INSERT OR REPLACE INTO outfit_states
            (user_id,outfit_id,favorite,in_pool,scene_ids_json,skip_count,hidden,updated_at)
            VALUES (:user_id,:outfit_id,:favorite,:in_pool,:scene_ids_json,:skip_count,:hidden,:updated_at)""",
            state,
        )

    def delete_outfit(self, outfit_id: str, user_id: Optional[str] = None) -> bool:
        outfit = self.get_outfit(outfit_id, user_id)
        if not outfit:
            return False
        with self.connect() as db:
            db.execute("DELETE FROM user_skip_events WHERE outfit_id=?", (outfit_id,))
            db.execute("DELETE FROM outfit_states WHERE outfit_id=?", (outfit_id,))
            if user_id:
                return bool(db.execute(
                    "DELETE FROM outfits WHERE id=? AND owner_user_id=?", (outfit_id, user_id)
                ).rowcount)
            return bool(db.execute("DELETE FROM outfits WHERE id=?", (outfit_id,)).rowcount)

    def save_outfit(
        self, payload: Dict[str, Any], outfit_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _now()
        identifier = outfit_id or _id("outfit")
        existing = self.get_outfit(identifier, user_id)
        source = payload.get("source", existing["source"] if existing else "manual")
        values = {
            "id": identifier,
            "label": payload.get("label", existing["label"] if existing else "我的穿搭"),
            "audience": payload.get("audience", existing["audience"] if existing else "mens"),
            "source": source,
            "components_json": json.dumps(
                payload.get("components", existing["components"] if existing else []), ensure_ascii=False
            ),
            "scene_ids_json": json.dumps(
                payload.get("scene_ids", existing["scene_ids"] if existing else ["commute"]),
                ensure_ascii=False,
            ),
            "suitable_min": payload.get("suitable_min", existing["suitable_min"] if existing else 15),
            "suitable_max": payload.get("suitable_max", existing["suitable_max"] if existing else 28),
            # Keep the retired database column at zero for backward-compatible SQLite files.
            "favorite": 0,
            "in_pool": int(payload.get("in_pool", existing["in_pool"] if existing else False)),
            "inspiration_id": payload.get("inspiration_id", existing["inspiration_id"] if existing else None),
            "skip_count": existing["skip_count"] if existing else 0,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
            "replication_json": json.dumps(
                payload.get("replication_guide", existing.get("replication_guide") if existing else {}),
                ensure_ascii=False,
            ),
            "analysis_json": json.dumps(
                payload.get("outfit_analysis", existing.get("outfit_analysis") if existing else {}),
                ensure_ascii=False,
            ),
            "owner_user_id": user_id,
        }
        with self.connect() as db:
            db.execute(
                """INSERT OR REPLACE INTO outfits
                (id,label,audience,source,components_json,scene_ids_json,suitable_min,suitable_max,
                 favorite,in_pool,inspiration_id,skip_count,created_at,updated_at,replication_json,
                 analysis_json,owner_user_id)
                VALUES (:id,:label,:audience,:source,:components_json,:scene_ids_json,:suitable_min,
                 :suitable_max,:favorite,:in_pool,:inspiration_id,:skip_count,:created_at,:updated_at,
                 :replication_json,:analysis_json,:owner_user_id)""",
                values,
            )
        return self.get_outfit(identifier, user_id)

    def update_outfit_status(
        self, outfit_id: str, payload: Dict[str, Any], user_id: str
    ) -> Optional[Dict[str, Any]]:
        outfit = self.get_outfit(outfit_id, user_id)
        if not outfit:
            return None
        return self.save_outfit(payload, outfit_id, user_id)

    def create_inspiration(
        self, payload: Dict[str, Any], user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        now = _now()
        row = {
            "id": _id("inspiration"), "status": "queued", "provider": "mock",
            "result_json": "{}", "created_at": now, "updated_at": now,
            "owner_user_id": user_id, **payload,
        }
        if user_id:
            row["upload_key"] = f"{user_id}:{row['upload_key']}"
        with self.connect() as db:
            db.execute(
                """INSERT INTO inspirations
                (id,upload_key,content_hash,original_name,media_type,file_path,status,provider,
                 result_json,created_at,updated_at,owner_user_id)
                VALUES (:id,:upload_key,:content_hash,:original_name,:media_type,:file_path,:status,
                 :provider,:result_json,:created_at,:updated_at,:owner_user_id)""",
                row,
            )
        return self.get_inspiration(row["id"], user_id)

    def get_inspiration_by_key(
        self, upload_key: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        key = f"{user_id}:{upload_key}" if user_id else upload_key
        with self.connect() as db:
            row = db.execute("SELECT * FROM inspirations WHERE upload_key=?", (key,)).fetchone()
        return self._inspiration(row) if row else None

    def set_inspiration_generated_name(
        self, inspiration_id: str, name: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        inspiration = self.get_owned_inspiration(inspiration_id, user_id)
        if not inspiration:
            return None
        result = inspiration["result"] | {"ai_generated_name": name[:30]}
        with self.connect() as db:
            db.execute(
                """UPDATE inspirations SET result_json=?,updated_at=?
                WHERE id=? AND owner_user_id=?""",
                (json.dumps(result, ensure_ascii=False), _now(), inspiration_id, user_id),
            )
        return self.get_owned_inspiration(inspiration_id, user_id)

    def get_owned_inspiration(
        self, inspiration_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM inspirations WHERE id=? AND owner_user_id=?",
                (inspiration_id, user_id),
            ).fetchone()
        return self._inspiration(row) if row else None

    def get_inspiration_by_hash(
        self, content_hash: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM inspirations WHERE content_hash=?"
        values: List[Any] = [content_hash]
        if user_id:
            query += " AND owner_user_id=?"
            values.append(user_id)
        query += " ORDER BY created_at LIMIT 1"
        with self.connect() as db:
            row = db.execute(query, values).fetchone()
        return self._inspiration(row) if row else None

    def get_inspiration(
        self, inspiration_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM inspirations WHERE id=?"
        values: List[Any] = [inspiration_id]
        if user_id:
            query += " AND owner_user_id=?"
            values.append(user_id)
        with self.connect() as db:
            row = db.execute(query, values).fetchone()
        return self._inspiration(row) if row else None

    def inspiration_path(
        self, inspiration_id: str, user_id: Optional[str] = None
    ) -> Optional[Path]:
        query = "SELECT file_path FROM inspirations WHERE id=?"
        values: List[Any] = [inspiration_id]
        if user_id:
            query += " AND owner_user_id=?"
            values.append(user_id)
        with self.connect() as db:
            row = db.execute(query, values).fetchone()
        return Path(row["file_path"]) if row else None

    def list_inspirations(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM inspirations"
        values: List[Any] = []
        if user_id:
            query += " WHERE owner_user_id=?"
            values.append(user_id)
        query += " ORDER BY created_at DESC"
        with self.connect() as db:
            return [self._inspiration(row) for row in db.execute(query, values)]

    @staticmethod
    def _inspiration(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        result.pop("owner_user_id", None)
        result["result"] = json.loads(result.pop("result_json"))
        result.pop("file_path", None)
        return result

    def set_analysis(
        self, inspiration_id: str, result: Dict[str, Any], provider: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        query = "UPDATE inspirations SET status='needs_review',provider=?,result_json=?,updated_at=? WHERE id=?"
        values: List[Any] = [provider, json.dumps(result, ensure_ascii=False), _now(), inspiration_id]
        if user_id:
            query += " AND owner_user_id=?"
            values.append(user_id)
        with self.connect() as db:
            db.execute(query, values)
        return self.get_inspiration(inspiration_id, user_id)

    def mark_inspiration_ready(self, inspiration_id: str, user_id: Optional[str] = None) -> None:
        query = "UPDATE inspirations SET status='ready',updated_at=? WHERE id=?"
        values: List[Any] = [_now(), inspiration_id]
        if user_id:
            query += " AND owner_user_id=?"
            values.append(user_id)
        with self.connect() as db:
            db.execute(query, values)

    def save_subscription(self, payload: Dict[str, str], user_id: str) -> Dict[str, Any]:
        now, identifier = _now(), _id("push")
        with self.connect() as db:
            db.execute(
                """INSERT INTO push_subscriptions
                (id,endpoint,p256dh,auth,enabled,last_result,updated_at,user_id)
                VALUES (?,?,?,?,1,NULL,?,?) ON CONFLICT(endpoint) DO UPDATE SET
                p256dh=excluded.p256dh,auth=excluded.auth,enabled=1,
                updated_at=excluded.updated_at,user_id=excluded.user_id""",
                (identifier, payload["endpoint"], payload["p256dh"], payload["auth"], now, user_id),
            )
            row = db.execute(
                """SELECT id,endpoint,enabled,last_result,updated_at FROM push_subscriptions
                WHERE endpoint=? AND user_id=?""",
                (payload["endpoint"], user_id),
            ).fetchone()
        result = dict(row)
        result["enabled"] = bool(result["enabled"])
        return result

    def enabled_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM push_subscriptions WHERE enabled=1 AND user_id=?", (user_id,)
            )]

    def set_subscription_result(
        self, subscription_id: str, result: str, user_id: str
    ) -> None:
        with self.connect() as db:
            db.execute(
                """UPDATE push_subscriptions SET last_result=?,updated_at=?
                WHERE id=? AND user_id=?""",
                (result, _now(), subscription_id, user_id),
            )

    def remove_subscription(self, subscription_id: str, user_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "DELETE FROM push_subscriptions WHERE id=? AND user_id=?",
                (subscription_id, user_id),
            )

    def get_delivery(self, key: str, user_id: str) -> Optional[Dict[str, Any]]:
        stored_key = f"{user_id}:{key}"
        with self.connect() as db:
            row = db.execute(
                """SELECT * FROM notification_deliveries
                WHERE idempotency_key=? AND user_id=?""",
                (stored_key, user_id),
            ).fetchone()
        if not row:
            return None
        result = dict(row) | {"deduplicated": True}
        result["idempotency_key"] = key
        return result

    def record_delivery(
        self, key: str, message: str, status: str, user_id: str
    ) -> Dict[str, Any]:
        existing = self.get_delivery(key, user_id)
        if existing:
            return existing
        row = {
            "id": _id("delivery"), "idempotency_key": f"{user_id}:{key}",
            "status": status, "message": message, "created_at": _now(), "user_id": user_id,
        }
        with self.connect() as db:
            db.execute(
                """INSERT INTO notification_deliveries
                (id,idempotency_key,status,message,created_at,user_id)
                VALUES (:id,:idempotency_key,:status,:message,:created_at,:user_id)""",
                row,
            )
        return row | {"deduplicated": False, "idempotency_key": key}

    def record_skip(self, outfit_id: str, local_date: str, user_id: str) -> Dict[str, Any]:
        outfit = self.get_outfit(outfit_id, user_id)
        with self.connect() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO user_skip_events VALUES (?,?,?,?)",
                (user_id, outfit_id, local_date, _now()),
            ).rowcount
            count = outfit["skip_count"] if outfit else 0
            if inserted:
                count += 1
                self._upsert_state(db, user_id, outfit_id, {"skip_count": count})
        return {
            "outfit_id": outfit_id, "skip_count": count, "prompt_remove": count >= 3,
            "counted_today": bool(inserted),
        }

    def get_ai_quota(self, user_id: str, local_date: str, usage_type: str) -> Dict[str, int]:
        limit = AI_USAGE_LIMITS[usage_type]
        with self.connect() as db:
            row = db.execute(
                """SELECT COUNT(*) AS count FROM analysis_events
                WHERE user_id=? AND local_date=? AND usage_type=?""",
                (user_id, local_date, usage_type),
            ).fetchone()
        used = int(row["count"]) if row else 0
        return {"limit": limit, "used": used, "remaining": max(0, limit - used)}

    def reserve_ai_usage(self, user_id: str, local_date: str, usage_type: str) -> Optional[str]:
        limit = AI_USAGE_LIMITS[usage_type]
        event_id = _id("ai")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT COUNT(*) AS count FROM analysis_events
                WHERE user_id=? AND local_date=? AND usage_type=?""",
                (user_id, local_date, usage_type),
            ).fetchone()
            if row and int(row["count"]) >= limit:
                return None
            db.execute(
                """INSERT INTO analysis_events
                (id, user_id, local_date, usage_type, created_at) VALUES (?,?,?,?,?)""",
                (event_id, user_id, local_date, usage_type, _now()),
            )
        return event_id

    def release_ai_usage(self, event_id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM analysis_events WHERE id=?", (event_id,))

    def get_ai_advice(self, user_id: str, recommendation_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute(
                "SELECT result_json FROM ai_advice_cache WHERE user_id=? AND recommendation_id=?",
                (user_id, recommendation_id),
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def set_ai_advice(
        self, user_id: str, recommendation_id: str, result: Dict[str, Any]
    ) -> None:
        with self.connect() as db:
            db.execute(
                """INSERT OR REPLACE INTO ai_advice_cache
                (user_id, recommendation_id, result_json, created_at) VALUES (?,?,?,?)""",
                (user_id, recommendation_id, json.dumps(result, ensure_ascii=False), _now()),
            )

    def get_ai_outfit_image(self, user_id: str, recommendation_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute(
                """SELECT file_path,created_at FROM ai_outfit_image_cache
                WHERE user_id=? AND recommendation_id=?""",
                (user_id, recommendation_id),
            ).fetchone()
        if not row or not Path(row["file_path"]).is_file():
            return None
        return dict(row)

    def set_ai_outfit_image(self, user_id: str, recommendation_id: str, image_data: bytes) -> str:
        digest = hashlib.sha256(image_data).hexdigest()
        file_path = ImageService(self.generated_dir).process_and_store(image_data, digest)["original"]
        with self.connect() as db:
            db.execute(
                """INSERT OR REPLACE INTO ai_outfit_image_cache
                (user_id,recommendation_id,file_path,created_at) VALUES (?,?,?,?)""",
                (user_id, recommendation_id, file_path, _now()),
            )
        return file_path

    def record_feedback(self, week_key: str, choice: str, user_id: str) -> Dict[str, Any]:
        current = self.get_settings(user_id)
        old = current["cold_offset"]
        delta = -2 if choice == "cold" else 2 if choice == "hot" else 0
        new = max(-6, min(6, old + delta))
        stored_key = f"{user_id}:{week_key}"
        with self.connect() as db:
            existing = db.execute(
                "SELECT * FROM feedback WHERE week_key=? AND user_id=?", (stored_key, user_id)
            ).fetchone()
            if existing:
                result = dict(existing) | {"deduplicated": True}
                result["week_key"] = week_key
                return result
            row = {
                "id": _id("feedback"), "week_key": stored_key, "choice": choice,
                "old_offset": old, "new_offset": new, "created_at": _now(), "user_id": user_id,
            }
            db.execute(
                """INSERT INTO feedback
                (id,week_key,choice,old_offset,new_offset,created_at,user_id)
                VALUES (:id,:week_key,:choice,:old_offset,:new_offset,:created_at,:user_id)""",
                row,
            )
        if new != old:
            self.save_settings({"cold_offset": new}, user_id)
        return row | {"deduplicated": False, "week_key": week_key}


store = Store()
