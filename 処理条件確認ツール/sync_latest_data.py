#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import sqlite3
import datetime
import traceback

try:
    import psycopg2
except ImportError:
    psycopg2 = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "db_config.json")
DEFAULT_SOURCE_TABLE = "source_processing"
DEFAULT_LOCAL_TABLE = "local_processing"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_str():
    return datetime.datetime.now().strftime(DATE_FORMAT)


def sanitize_table_name(name, fallback):
    import re
    if not name:
        return fallback
    if re.match(r"^[A-Za-z0-9_]+$", name):
        return name
    return fallback


def load_config():
    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as file_handle:
            config = json.load(file_handle)
    source_config = config.get("source", {})
    local_config = config.get("local", {})
    source_path = source_config.get("path", "local.db")
    local_path = local_config.get("path", "local.db")
    source_table = sanitize_table_name(
        source_config.get("table"), DEFAULT_SOURCE_TABLE
    )
    local_table = sanitize_table_name(
        local_config.get("table"), DEFAULT_LOCAL_TABLE
    )
    connect_db = str(config.get("connect_db", "sqlite")).lower()
    if connect_db not in ("sqlite", "postgresql"):
        connect_db = "sqlite"

    postgresql_config = config.get("db", {}) if isinstance(config.get("db"), dict) else {}

    return {
        "connect_db": connect_db,
        "source_path": os.path.join(BASE_DIR, source_path),
        "local_path": os.path.join(BASE_DIR, local_path),
        "source_table": source_table,
        "local_table": local_table,
        "seed_sample_data": bool(source_config.get("seed_sample_data", True)),
        "postgresql": postgresql_config,
    }


def get_source_connection(config):
    connect_db = config.get("connect_db", "sqlite")
    if connect_db == "postgresql":
        if psycopg2 is None:
            raise RuntimeError(
                "connect_db=postgresql が設定されていますが、psycopg2 がインストールされていません。"
            )
        db_config = config.get("postgresql", {})
        options = db_config.get("options") or {}
        return psycopg2.connect(
            host=db_config.get("host"),
            port=db_config.get("port", 5432),
            dbname=db_config.get("database"),
            user=db_config.get("user"),
            password=db_config.get("password"),
            **options,
        )

    return sqlite3.connect(config["source_path"])


def get_sqlite_connection(db_path):
    return sqlite3.connect(db_path)


def init_db(conn, source_table=None, local_table=None, should_seed_sample=True, connect_db="sqlite"):
    cursor = conn.cursor()
    if source_table:
        if connect_db == "sqlite":
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {source_table} (
                    device_name TEXT NOT NULL,
                    condition_name TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(f"SELECT COUNT(*) FROM {source_table}")
            if should_seed_sample and cursor.fetchone()[0] == 0:
                seed_sample_data(cursor, source_table)

    if local_table:
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {local_table} (
                device_name TEXT NOT NULL,
                condition_name TEXT NOT NULL,
                latest_processed_at TEXT NOT NULL,
                confirmed_at TEXT NOT NULL,
                PRIMARY KEY (device_name, condition_name)
            )
            """
        )
    conn.commit()


def seed_sample_data(cursor, source_table):
    sample_rows = [
        ("装置A", "条件1", "2026-03-01 08:00:00"),
        ("装置A", "条件1", "2026-03-01 12:30:00"),
        ("装置A", "条件2", "2026-03-01 09:15:00"),
        ("装置B", "条件1", "2026-03-01 07:45:00"),
        ("装置B", "条件2", "2026-03-01 10:20:00"),
        ("装置B", "条件2", "2026-03-01 13:05:00"),
        ("装置C", "条件3", "2026-03-01 06:10:00"),
    ]
    cursor.executemany(
        f"""
        INSERT INTO {source_table} (device_name, condition_name, processed_at)
        VALUES (?, ?, ?)
        """,
        sample_rows,
    )


def fetch_latest_source(conn, source_table):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT device_name, condition_name, MAX(processed_at) AS latest_processed_at
        FROM {source_table}
        GROUP BY device_name, condition_name
        """
    )
    return cursor.fetchall()


def upsert_local(conn, latest_rows, local_table):
    cursor = conn.cursor()
    for device_name, condition_name, latest_processed_at in latest_rows:
        cursor.execute(
            f"""
            SELECT latest_processed_at
            FROM {local_table}
            WHERE device_name = ? AND condition_name = ?
            """,
            (device_name, condition_name),
        )
        existing = cursor.fetchone()
        if existing is None:
            cursor.execute(
                f"""
                INSERT INTO {local_table} (
                    device_name, condition_name, latest_processed_at, confirmed_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (device_name, condition_name, latest_processed_at, latest_processed_at),
            )
        else:
            cursor.execute(
                f"""
                UPDATE {local_table}
                SET latest_processed_at = ?
                WHERE device_name = ? AND condition_name = ?
                """,
                (latest_processed_at, device_name, condition_name),

            )
    conn.commit()


def sync_latest_data():
    """最新処理日時を同期するメイン処理"""
    config = load_config()
    source_conn = get_source_connection(config)
    local_conn = get_sqlite_connection(config["local_path"])
    try:
        init_db(
            source_conn,
            source_table=config["source_table"],
            should_seed_sample=config["seed_sample_data"],
            connect_db=config["connect_db"],
        )
        init_db(local_conn, local_table=config["local_table"])
        
        latest_rows = fetch_latest_source(source_conn, config["source_table"])
        upsert_local(local_conn, latest_rows, config["local_table"])
        
        print(f"同期完了: {len(latest_rows)}件のデータを処理しました。")
        return True
    except Exception as e:
        print(f"同期エラー: {e}")
        traceback.print_exc()
        return False
    finally:
        source_conn.close()
        local_conn.close()


if __name__ == "__main__":
    success = sync_latest_data()
    sys.exit(0 if success else 1)
