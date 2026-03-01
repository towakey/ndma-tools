import sys
import io
import os
import sqlite3
import datetime
import html
import json
import re

import cgi
import cgitb

cgitb.enable()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "db_config.json")
DEFAULT_SOURCE_TABLE = "source_processing"
DEFAULT_LOCAL_TABLE = "local_processing"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_str():
    return datetime.datetime.now().strftime(DATE_FORMAT)


def get_connection(db_path):
    return sqlite3.connect(db_path)


def sanitize_table_name(name, fallback):
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
    return {
        "source_path": os.path.join(BASE_DIR, source_path),
        "local_path": os.path.join(BASE_DIR, local_path),
        "source_table": source_table,
        "local_table": local_table,
        "seed_sample_data": bool(source_config.get("seed_sample_data", True)),
    }


def init_db(conn, source_table=None, local_table=None, seed_sample_data=True):
    cursor = conn.cursor()
    if source_table:
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
        if seed_sample_data and cursor.fetchone()[0] == 0:
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


def update_confirmed_at(conn, device_name, condition_name, local_table):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        UPDATE {local_table}
        SET confirmed_at = ?
        WHERE device_name = ? AND condition_name = ?
        """,
        (now_str(), device_name, condition_name),
    )
    conn.commit()


def fetch_local_sorted(conn, local_table):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT device_name, condition_name, latest_processed_at, confirmed_at
        FROM {local_table}
        ORDER BY device_name ASC, condition_name ASC
        """
    )
    return cursor.fetchall()


def render_html(rows, message):
    print("Content-Type: text/html; charset=utf-8\n")
    print("<!DOCTYPE html>")
    print("<html lang=\"ja\">")
    print("<head>")
    print("<meta charset=\"utf-8\">")
    print("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
    print("<title>処理条件確認ツール</title>")
    print("""
    <style>
        :root {
            --bg: #f2f1ec;
            --card: #ffffff;
            --ink: #1f2a30;
            --muted: #637179;
            --accent: #2f6f78;
            --accent-dark: #24565d;
        }
        body {
            margin: 0;
            font-family: "Meiryo", "Yu Gothic", "Segoe UI", sans-serif;
            background: var(--bg);
            color: var(--ink);
        }
        header {
            background: linear-gradient(135deg, #284a51, #3e7f88);
            color: #fff;
            padding: 24px 16px;
        }
        header h1 {
            margin: 0;
            font-size: 22px;
            letter-spacing: 0.04em;
        }
        main {
            max-width: 980px;
            margin: 24px auto;
            padding: 0 16px 32px;
        }
        .card {
            background: var(--card);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
        }
        .message {
            margin-bottom: 16px;
            color: var(--muted);
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 10px;
            border-bottom: 1px solid #e3e3e0;
            text-align: left;
            font-size: 14px;
        }
        th {
            background: #f8f8f6;
            font-weight: 600;
        }
        .btn {
            background: var(--accent);
            color: #fff;
            border: none;
            border-radius: 999px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 13px;
        }
        .btn:hover {
            background: var(--accent-dark);
        }
        .empty {
            text-align: center;
            color: var(--muted);
            padding: 24px 0;
        }
        @media (max-width: 720px) {
            th:nth-child(3), td:nth-child(3), th:nth-child(4), td:nth-child(4) {
                display: none;
            }
            header h1 {
                font-size: 18px;
            }
        }
    </style>
    """)
    print("</head>")
    print("<body>")
    print("<header><h1>処理条件確認ツール</h1></header>")
    print("<main>")
    print("<div class=\"card\">")
    print(f"<div class=\"message\">{html.escape(message)}</div>")
    print("<table>")
    print("<thead><tr><th>装置名</th><th>処理条件名</th><th>最新処理日時</th><th>確認日時</th><th>確認</th></tr></thead>")
    print("<tbody>")
    if rows:
        for device_name, condition_name, latest_processed_at, confirmed_at in rows:
            safe_device = html.escape(device_name)
            safe_condition = html.escape(condition_name)
            safe_latest = html.escape(latest_processed_at)
            safe_confirmed = html.escape(confirmed_at)
            print("<tr>")
            print(f"<td>{safe_device}</td>")
            print(f"<td>{safe_condition}</td>")
            print(f"<td>{safe_latest}</td>")
            print(f"<td>{safe_confirmed}</td>")
            print("<td>")
            print("<form method=\"post\" style=\"margin:0\">")
            print("<input type=\"hidden\" name=\"action\" value=\"confirm\">")
            print(f"<input type=\"hidden\" name=\"device_name\" value=\"{safe_device}\">")
            print(f"<input type=\"hidden\" name=\"condition_name\" value=\"{safe_condition}\">")
            print("<button class=\"btn\" type=\"submit\">確認</button>")
            print("</form>")
            print("</td>")
            print("</tr>")
    else:
        print("<tr><td class=\"empty\" colspan=\"5\">データがありません。</td></tr>")
    print("</tbody></table>")
    print("</div>")
    print("</main>")
    print("</body>")
    print("</html>")


def main():
    # これを使用しないと日本語が文字化けする
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    form = cgi.FieldStorage()
    action = form.getfirst("action", "")
    device_name = form.getfirst("device_name", "")
    condition_name = form.getfirst("condition_name", "")

    message = "SQLiteサンプルDBを作成し、最新処理日時を取得しています。"

    config = load_config()
    source_conn = get_connection(config["source_path"])
    local_conn = get_connection(config["local_path"])
    try:
        init_db(
            source_conn,
            source_table=config["source_table"],
            seed_sample_data=config["seed_sample_data"],
        )

        init_db(local_conn, local_table=config["local_table"])
        if action == "confirm" and device_name and condition_name:
            update_confirmed_at(local_conn, device_name, condition_name, config["local_table"])
            message = f"{device_name} / {condition_name} の確認日時を更新しました。"

        latest_rows = fetch_latest_source(source_conn, config["source_table"])
        upsert_local(local_conn, latest_rows, config["local_table"])
        local_rows = fetch_local_sorted(local_conn, config["local_table"])

    finally:
        source_conn.close()
        local_conn.close()

    render_html(local_rows, message)


if __name__ == "__main__":
    main()