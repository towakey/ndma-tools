import sys
import io
import os
import csv
import json
import html
import sqlite3
import traceback
import datetime
import urllib.parse
import shutil
import subprocess

import cgi
import cgitb
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
STATIC_FILES = {
    "app.css": ("text/css; charset=utf-8", "app.css"),
    "app.js": ("application/javascript; charset=utf-8", "app.js"),
}
MYSQL_CLIENT_CANDIDATES = [
    r"C:\xampp\mysql\bin\mysql.exe",
    "mysql",
]
POSTGRES_CLIENT_CANDIDATES = [
    "psql",
]


def configure_output():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def setup_cgitb():
    try:
        cgitb.enable(display=0, logdir=BASE_DIR)
    except Exception:
        cgitb.enable(display=0)


def now_str():
    return datetime.datetime.now().strftime(DATE_FORMAT)


def ensure_dirs():
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            table_name TEXT NOT NULL UNIQUE,
            encoding TEXT NOT NULL,
            row_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'csv',
            source_config TEXT NOT NULL DEFAULT '',
            source_query TEXT NOT NULL DEFAULT '',
            last_refreshed_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER NOT NULL,
            field_key TEXT NOT NULL,
            original_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            FOREIGN KEY(dataset_id) REFERENCES datasets(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            left_dataset_id INTEGER NOT NULL,
            left_field_id INTEGER NOT NULL,
            right_dataset_id INTEGER NOT NULL,
            right_field_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(left_dataset_id) REFERENCES datasets(id),
            FOREIGN KEY(left_field_id) REFERENCES dataset_fields(id),
            FOREIGN KEY(right_dataset_id) REFERENCES datasets(id),
            FOREIGN KEY(right_field_id) REFERENCES dataset_fields(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS link_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS link_template_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            relation_id INTEGER NOT NULL,
            left_field_id INTEGER,
            right_field_id INTEGER,
            sort_order INTEGER NOT NULL,
            FOREIGN KEY(template_id) REFERENCES link_templates(id),
            FOREIGN KEY(relation_id) REFERENCES relations(id)
        )
        """
    )
    cursor.execute("PRAGMA table_info(link_template_relations)")
    template_relation_columns = [row[1] for row in cursor.fetchall()]
    if "left_field_id" not in template_relation_columns:
        cursor.execute("ALTER TABLE link_template_relations ADD COLUMN left_field_id INTEGER")
    if "right_field_id" not in template_relation_columns:
        cursor.execute("ALTER TABLE link_template_relations ADD COLUMN right_field_id INTEGER")
    cursor.execute("PRAGMA table_info(datasets)")
    dataset_columns = [row[1] for row in cursor.fetchall()]
    if "source_type" not in dataset_columns:
        cursor.execute("ALTER TABLE datasets ADD COLUMN source_type TEXT NOT NULL DEFAULT 'csv'")
    if "source_config" not in dataset_columns:
        cursor.execute("ALTER TABLE datasets ADD COLUMN source_config TEXT NOT NULL DEFAULT ''")
    if "source_query" not in dataset_columns:
        cursor.execute("ALTER TABLE datasets ADD COLUMN source_query TEXT NOT NULL DEFAULT ''")
    if "last_refreshed_at" not in dataset_columns:
        cursor.execute("ALTER TABLE datasets ADD COLUMN last_refreshed_at TEXT NOT NULL DEFAULT ''")
    cursor.execute("UPDATE datasets SET source_type = 'csv' WHERE source_type IS NULL OR source_type = ''")
    cursor.execute("UPDATE datasets SET source_config = '' WHERE source_config IS NULL")
    cursor.execute("UPDATE datasets SET source_query = '' WHERE source_query IS NULL")
    cursor.execute("UPDATE datasets SET last_refreshed_at = created_at WHERE last_refreshed_at IS NULL OR last_refreshed_at = ''")
    conn.commit()


def parse_form():
    return cgi.FieldStorage()


def html_escape(value):
    return html.escape(str(value), quote=True)


def quote_identifier(name):
    if not name:
        raise ValueError("識別子が空です。")
    return '"' + str(name).replace('"', '""') + '"'


def next_table_name(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM datasets")
    next_id = cursor.fetchone()[0]
    return "data_{0}".format(next_id)


def next_field_key(existing_field_keys):
    max_index = 0
    for field_key in existing_field_keys:
        text = str(field_key or "")
        if not text.startswith("col_"):
            continue
        try:
            max_index = max(max_index, int(text[4:]))
        except ValueError:
            continue
    return "col_{0:03d}".format(max_index + 1)


def normalize_headers(headers):
    normalized = []
    for index, value in enumerate(headers):
        header = str(value).strip() if value is not None else ""
        normalized.append(header or "列{0}".format(index + 1))
    return normalized


def find_mysql_client_path():
    for candidate in MYSQL_CLIENT_CANDIDATES:
        if os.path.isabs(candidate) and os.path.exists(candidate):
            return candidate
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise ValueError("MySQLクライアントが見つかりません。XAMPPのMySQLが利用できる状態か確認してください.")


def find_postgresql_client_path():
    for candidate in POSTGRES_CLIENT_CANDIDATES:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    program_dirs = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]
    for base_dir in program_dirs:
        postgres_root = os.path.join(base_dir, "PostgreSQL")
        if not os.path.isdir(postgres_root):
            continue
        for version_name in sorted(os.listdir(postgres_root), reverse=True):
            candidate_path = os.path.join(postgres_root, version_name, "bin", "psql.exe")
            if os.path.exists(candidate_path):
                return candidate_path
    raise ValueError("PostgreSQLクライアントが見つかりません。psql が利用できる状態か確認してください。")


def build_source_config_text(source_config):
    return json.dumps(source_config, ensure_ascii=False)


def parse_source_config_text(source_config_text):
    if not source_config_text:
        return {}
    try:
        parsed = json.loads(source_config_text)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def format_mysql_source_label(source_config):
    host = str(source_config.get("host", "localhost") or "localhost").strip() or "localhost"
    port = str(source_config.get("port", "3306") or "3306").strip() or "3306"
    database_name = str(source_config.get("database", "") or "").strip()
    user = str(source_config.get("user", "") or "").strip()
    parts = ["{0}:{1}".format(host, port)]
    if database_name:
        parts.append(database_name)
    if user:
        parts.append(user)
    return " / ".join(parts)


def format_postgresql_source_label(source_config):
    return format_mysql_source_label(source_config)


def detect_encoding(raw_bytes):
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            raw_bytes.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("CSVの文字コードを判定できませんでした。UTF-8 または CP932 を使用してください。")


def sanitize_query_text(query_text):
    normalized_query = (query_text or "").strip()
    if not normalized_query:
        raise ValueError("取得クエリを入力してください。")
    while normalized_query.endswith(";"):
        normalized_query = normalized_query[:-1].rstrip()
    if not normalized_query:
        raise ValueError("取得クエリを入力してください。")
    if ";" in normalized_query:
        raise ValueError("取得クエリは1文のみ指定してください。")
    first_token = normalized_query.split(None, 1)[0].lower()
    if first_token not in ("select", "with"):
        raise ValueError("取得クエリはSELECTまたはWITHで始めてください。")
    return normalized_query


def mysql_cli_unescape(value):
    escaped_map = {
        "0": "\0",
        "b": "\b",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "Z": "\x1a",
        "\\": "\\",
    }
    result = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            next_char = value[index + 1]
            if next_char == "N":
                result.append("")
                index += 2
                continue
            if next_char in escaped_map:
                result.append(escaped_map[next_char])
                index += 2
                continue
        result.append(char)
        index += 1
    return "".join(result)


def parse_mysql_batch_output(output_text):
    reader = csv.reader(io.StringIO(output_text), delimiter="\t")
    rows = list(reader)
    if not rows:
        raise ValueError("クエリ結果が取得できませんでした。")
    headers = normalize_headers([mysql_cli_unescape(value) for value in rows[0]])
    data_rows = []
    width = len(headers)
    for row in rows[1:]:
        values = [mysql_cli_unescape(value) for value in list(row[:width])]
        while len(values) < width:
            values.append("")
        data_rows.append(values)
    return headers, data_rows


def parse_csv_output(output_text):
    reader = csv.reader(io.StringIO(output_text))
    rows = list(reader)
    if not rows:
        raise ValueError("クエリ結果が取得できませんでした。")
    headers = normalize_headers(rows[0])
    data_rows = rows[1:]
    return headers, data_rows


def run_mysql_query(source_config, query_text):
    mysql_client_path = find_mysql_client_path()
    host = str(source_config.get("host", "localhost") or "localhost").strip() or "localhost"
    port_text = str(source_config.get("port", "3306") or "3306").strip() or "3306"
    database_name = str(source_config.get("database", "") or "").strip()
    user = str(source_config.get("user", "") or "").strip()
    password = str(source_config.get("password", "") or "")
    if not database_name:
        raise ValueError("データベース名を入力してください。")
    if not user:
        raise ValueError("ユーザー名を入力してください。")
    try:
        port = int(port_text)
    except ValueError:
        raise ValueError("ポート番号は数値で入力してください。")
    command = [
        mysql_client_path,
        "--batch",
        "--default-character-set=utf8mb4",
        "--host",
        host,
        "--port",
        str(port),
        "--user",
        user,
        "--database",
        database_name,
        "--execute",
        query_text,
    ]
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password
    else:
        env.pop("MYSQL_PWD", None)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("MySQLクエリの実行がタイムアウトしました。")
    except OSError as exc:
        raise ValueError("MySQLクライアントを実行できませんでした: {0}".format(exc))
    if completed.returncode != 0:
        error_message = (completed.stderr or completed.stdout).strip()
        raise ValueError(error_message or "MySQLクエリの実行に失敗しました。")
    return parse_mysql_batch_output(completed.stdout)


def run_postgresql_query(source_config, query_text):
    postgresql_client_path = find_postgresql_client_path()
    host = str(source_config.get("host", "localhost") or "localhost").strip() or "localhost"
    port_text = str(source_config.get("port", "5432") or "5432").strip() or "5432"
    database_name = str(source_config.get("database", "") or "").strip()
    user = str(source_config.get("user", "") or "").strip()
    password = str(source_config.get("password", "") or "")
    if not database_name:
        raise ValueError("データベース名を入力してください。")
    if not user:
        raise ValueError("ユーザー名を入力してください。")
    try:
        port = int(port_text)
    except ValueError:
        raise ValueError("ポート番号は数値で入力してください。")
    copy_sql = "COPY ({0}) TO STDOUT WITH (FORMAT CSV, HEADER TRUE)".format(query_text)
    command = [
        postgresql_client_path,
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        database_name,
        "-c",
        copy_sql,
    ]
    env = os.environ.copy()
    env["PGCLIENTENCODING"] = "UTF8"
    if password:
        env["PGPASSWORD"] = password
    else:
        env.pop("PGPASSWORD", None)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("PostgreSQLクエリの実行がタイムアウトしました。")
    except OSError as exc:
        raise ValueError("PostgreSQLクライアントを実行できませんでした: {0}".format(exc))
    if completed.returncode != 0:
        error_message = (completed.stderr or completed.stdout).strip()
        raise ValueError(error_message or "PostgreSQLクエリの実行に失敗しました。")
    return parse_csv_output(completed.stdout)


def load_csv_rows(file_item):
    raw_bytes = file_item.file.read()
    if not raw_bytes:
        raise ValueError("CSVファイルが空です。")
    encoding = detect_encoding(raw_bytes)
    text = raw_bytes.decode(encoding)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError("CSVにデータがありません。")
    headers = normalize_headers(rows[0])
    data_rows = rows[1:]
    return encoding, headers, data_rows


def create_dataset_storage(cursor, table_name, field_keys):
    create_table_sql = "CREATE TABLE {0} (row_id INTEGER PRIMARY KEY AUTOINCREMENT".format(
        quote_identifier(table_name)
    )
    for field_key in field_keys:
        create_table_sql += ", {0} TEXT".format(quote_identifier(field_key))
    create_table_sql += ")"
    cursor.execute(create_table_sql)


def insert_dataset_rows(cursor, table_name, field_keys, data_rows):
    if not data_rows:
        return
    placeholders = ", ".join(["?"] * len(field_keys))
    insert_sql = "INSERT INTO {0} ({1}) VALUES ({2})".format(
        quote_identifier(table_name),
        ", ".join(quote_identifier(field_key) for field_key in field_keys),
        placeholders,
    )
    normalized_rows = []
    width = len(field_keys)
    for row in data_rows:
        values = []
        for value in list(row[:width]):
            values.append("" if value is None else str(value))
        while len(values) < width:
            values.append("")
        normalized_rows.append(values)
    cursor.executemany(insert_sql, normalized_rows)


def create_dataset(conn, dataset_name, original_filename, encoding, headers, data_rows, source_type="csv", source_config_text="", source_query="", last_refreshed_at=""):
    cursor = conn.cursor()
    table_name = next_table_name(conn)
    created_at = now_str()
    refreshed_at = last_refreshed_at or created_at
    headers = normalize_headers(headers)
    if not headers:
        raise ValueError("列情報がありません。")
    row_count = len(data_rows)
    cursor.execute(
        """
        INSERT INTO datasets (name, original_filename, table_name, encoding, row_count, created_at, source_type, source_config, source_query, last_refreshed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (dataset_name, original_filename, table_name, encoding, row_count, created_at, source_type, source_config_text, source_query, refreshed_at),
    )
    dataset_id = cursor.lastrowid

    field_keys = []
    for index, header in enumerate(headers):
        field_key = next_field_key(field_keys)
        field_keys.append(field_key)
        cursor.execute(
            """
            INSERT INTO dataset_fields (dataset_id, field_key, original_name, display_name, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (dataset_id, field_key, header, header, index),
        )

    create_dataset_storage(cursor, table_name, field_keys)
    insert_dataset_rows(cursor, table_name, field_keys, data_rows)
    conn.commit()


def get_datasets(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, original_filename, table_name, encoding, row_count, created_at, source_type, source_config, source_query, last_refreshed_at
        FROM datasets
        ORDER BY created_at DESC, id DESC
        """
    )
    return cursor.fetchall()


def get_dataset(conn, dataset_id):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, original_filename, table_name, encoding, row_count, created_at, source_type, source_config, source_query, last_refreshed_at
        FROM datasets
        WHERE id = ?
        """,
        (dataset_id,),
    )
    return cursor.fetchone()


def seed_samples_if_needed(conn):
    datasets = get_datasets(conn)
    if datasets:
        return False
    if not os.path.exists(SAMPLES_DIR):
        return False

    sample_files = []
    for name in sorted(os.listdir(SAMPLES_DIR)):
        if not name.lower().endswith(".csv"):
            continue
        sample_files.append(os.path.join(SAMPLES_DIR, name))

    if not sample_files:
        return False

    for sample_path in sample_files:
        with open(sample_path, "rb") as file_handle:
            raw_bytes = file_handle.read()
        encoding = detect_encoding(raw_bytes)
        text = raw_bytes.decode(encoding)
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            continue
        headers = normalize_headers(rows[0])
        data_rows = rows[1:]
        dataset_name = os.path.splitext(os.path.basename(sample_path))[0]
        create_dataset(
            conn,
            dataset_name,
            os.path.basename(sample_path),
            encoding,
            headers,
            data_rows,
        )
    return True


def get_dataset_fields(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, dataset_id, field_key, original_name, display_name, sort_order
        FROM dataset_fields
        ORDER BY dataset_id ASC, sort_order ASC, id ASC
        """
    )
    return cursor.fetchall()


def get_dataset_samples(conn, limit_per_dataset=3):
    datasets = get_datasets(conn)
    fields = get_dataset_fields(conn)
    field_map = {}
    for field in fields:
        field_map.setdefault(field["dataset_id"], []).append(field)
    samples = {}
    cursor = conn.cursor()
    for dataset in datasets:
        dataset_fields = field_map.get(dataset["id"], [])
        if not dataset_fields:
            samples[dataset["id"]] = []
            continue
        column_sql = ", ".join(quote_identifier(field["field_key"]) for field in dataset_fields)
        query = "SELECT {0} FROM {1} ORDER BY row_id ASC LIMIT ?".format(
            column_sql,
            quote_identifier(dataset["table_name"]),
        )
        cursor.execute(query, (limit_per_dataset,))
        samples[dataset["id"]] = cursor.fetchall()
    return samples


def rename_dataset(conn, dataset_id, new_name):
    cursor = conn.cursor()
    cursor.execute("UPDATE datasets SET name = ? WHERE id = ?", (new_name, dataset_id))
    conn.commit()


def delete_dataset(conn, dataset_id):
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM datasets WHERE id = ?", (dataset_id,))
    row = cursor.fetchone()
    if row is None:
        return
    table_name = row["table_name"]
    cursor.execute(
        "DELETE FROM link_template_relations WHERE relation_id IN (SELECT id FROM relations WHERE left_dataset_id = ? OR right_dataset_id = ?)",
        (dataset_id, dataset_id),
    )
    cursor.execute(
        "DELETE FROM link_template_relations WHERE left_field_id IN (SELECT id FROM dataset_fields WHERE dataset_id = ?) OR right_field_id IN (SELECT id FROM dataset_fields WHERE dataset_id = ?)",
        (dataset_id, dataset_id),
    )
    cursor.execute("DELETE FROM relations WHERE left_dataset_id = ? OR right_dataset_id = ?", (dataset_id, dataset_id))
    cursor.execute("DELETE FROM dataset_fields WHERE dataset_id = ?", (dataset_id,))
    cursor.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
    cursor.execute("DROP TABLE IF EXISTS {0}".format(quote_identifier(table_name)))
    conn.commit()


def delete_field_dependencies(cursor, field_ids):
    if not field_ids:
        return
    placeholders = ", ".join(["?"] * len(field_ids))
    params = tuple(field_ids)
    cursor.execute(
        "DELETE FROM link_template_relations WHERE relation_id IN (SELECT id FROM relations WHERE left_field_id IN ({0}) OR right_field_id IN ({0}))".format(placeholders),
        params + params,
    )
    cursor.execute(
        "DELETE FROM link_template_relations WHERE left_field_id IN ({0}) OR right_field_id IN ({0})".format(placeholders),
        params + params,
    )
    cursor.execute(
        "DELETE FROM relations WHERE left_field_id IN ({0}) OR right_field_id IN ({0})".format(placeholders),
        params + params,
    )
    cursor.execute(
        "DELETE FROM dataset_fields WHERE id IN ({0})".format(placeholders),
        params,
    )


def refresh_dataset(conn, dataset_id, original_filename, encoding, headers, data_rows, source_type=None, source_config_text=None, source_query=None):
    dataset = get_dataset(conn, dataset_id)
    if dataset is None:
        raise ValueError("更新対象のデータが見つかりません。")
    headers = normalize_headers(headers)
    if not headers:
        raise ValueError("列情報がありません。")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, dataset_id, field_key, original_name, display_name, sort_order
        FROM dataset_fields
        WHERE dataset_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (dataset_id,),
    )
    existing_fields = cursor.fetchall()
    existing_by_name = {}
    for field in existing_fields:
        existing_by_name.setdefault(field["original_name"], []).append(field)
    matched_field_ids = set()
    current_field_keys = [field["field_key"] for field in existing_fields]
    final_field_keys = []
    for index, header in enumerate(headers):
        matched_field = None
        for field in existing_by_name.get(header, []):
            if field["id"] not in matched_field_ids:
                matched_field = field
                break
        if matched_field is not None:
            matched_field_ids.add(matched_field["id"])
            cursor.execute(
                "UPDATE dataset_fields SET original_name = ?, sort_order = ? WHERE id = ?",
                (header, index, matched_field["id"]),
            )
            final_field_keys.append(matched_field["field_key"])
            continue
        field_key = next_field_key(current_field_keys)
        current_field_keys.append(field_key)
        cursor.execute(
            """
            INSERT INTO dataset_fields (dataset_id, field_key, original_name, display_name, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (dataset_id, field_key, header, header, index),
        )
        final_field_keys.append(field_key)
    removed_field_ids = [field["id"] for field in existing_fields if field["id"] not in matched_field_ids]
    delete_field_dependencies(cursor, removed_field_ids)
    cursor.execute("DROP TABLE IF EXISTS {0}".format(quote_identifier(dataset["table_name"])))
    create_dataset_storage(cursor, dataset["table_name"], final_field_keys)
    insert_dataset_rows(cursor, dataset["table_name"], final_field_keys, data_rows)
    cursor.execute(
        """
        UPDATE datasets
        SET original_filename = ?, encoding = ?, row_count = ?, source_type = ?, source_config = ?, source_query = ?, last_refreshed_at = ?
        WHERE id = ?
        """,
        (
            original_filename,
            encoding,
            len(data_rows),
            source_type if source_type is not None else dataset["source_type"],
            source_config_text if source_config_text is not None else dataset["source_config"],
            source_query if source_query is not None else dataset["source_query"],
            now_str(),
            dataset_id,
        ),
    )
    conn.commit()


def parse_mysql_source_form(form):
    return parse_db_source_form(form, "mysql")


def parse_db_source_form(form, forced_db_type=""):
    db_type = (forced_db_type or form.getfirst("db_type", "mysql")).strip().lower() or "mysql"
    if db_type not in ("mysql", "postgresql"):
        raise ValueError("DB種別が不正です。")
    default_port = "5432" if db_type == "postgresql" else "3306"
    host = form.getfirst("db_host", "localhost").strip() or "localhost"
    port_text = form.getfirst("db_port", default_port).strip() or default_port
    database_name = form.getfirst("db_name", "").strip()
    user = form.getfirst("db_user", "").strip()
    password = form.getfirst("db_password", "")
    if not database_name:
        raise ValueError("データベース名を入力してください。")
    if not user:
        raise ValueError("ユーザー名を入力してください。")
    try:
        int(port_text)
    except ValueError:
        raise ValueError("ポート番号は数値で入力してください。")
    return {
        "db_type": db_type,
        "host": host,
        "port": port_text,
        "database": database_name,
        "user": user,
        "password": password,
    }


def register_mysql_dataset(conn, dataset_name, source_config, query_text):
    sanitized_query = sanitize_query_text(query_text)
    headers, data_rows = run_mysql_query(source_config, sanitized_query)
    create_dataset(
        conn,
        dataset_name,
        "MySQLクエリ",
        "utf-8",
        headers,
        data_rows,
        source_type="mysql_query",
        source_config_text=build_source_config_text(source_config),
        source_query=sanitized_query,
    )
    return len(data_rows)


def register_postgresql_dataset(conn, dataset_name, source_config, query_text):
    sanitized_query = sanitize_query_text(query_text)
    headers, data_rows = run_postgresql_query(source_config, sanitized_query)
    create_dataset(
        conn,
        dataset_name,
        "PostgreSQLクエリ",
        "utf-8",
        headers,
        data_rows,
        source_type="postgresql_query",
        source_config_text=build_source_config_text(source_config),
        source_query=sanitized_query,
    )
    return len(data_rows)


def register_db_dataset(conn, dataset_name, source_config, query_text):
    if source_config["db_type"] == "mysql":
        return register_mysql_dataset(conn, dataset_name, source_config, query_text)
    if source_config["db_type"] == "postgresql":
        return register_postgresql_dataset(conn, dataset_name, source_config, query_text)
    raise ValueError("DB種別が不正です。")


def refresh_mysql_dataset(conn, dataset_id):
    dataset = get_dataset(conn, dataset_id)
    if dataset is None:
        raise ValueError("更新対象のデータが見つかりません。")
    if dataset["source_type"] != "mysql_query":
        raise ValueError("このデータはDB更新に対応していません。")
    source_config = parse_source_config_text(dataset["source_config"])
    sanitized_query = sanitize_query_text(dataset["source_query"])
    headers, data_rows = run_mysql_query(source_config, sanitized_query)
    refresh_dataset(
        conn,
        dataset_id,
        dataset["original_filename"],
        "utf-8",
        headers,
        data_rows,
    )
    return len(data_rows)


def refresh_postgresql_dataset(conn, dataset_id):
    dataset = get_dataset(conn, dataset_id)
    if dataset is None:
        raise ValueError("更新対象のデータが見つかりません。")
    if dataset["source_type"] != "postgresql_query":
        raise ValueError("このデータはDB更新に対応していません。")
    source_config = parse_source_config_text(dataset["source_config"])
    sanitized_query = sanitize_query_text(dataset["source_query"])
    headers, data_rows = run_postgresql_query(source_config, sanitized_query)
    refresh_dataset(
        conn,
        dataset_id,
        dataset["original_filename"],
        "utf-8",
        headers,
        data_rows,
    )
    return len(data_rows)


def refresh_db_dataset(conn, dataset_id):
    dataset = get_dataset(conn, dataset_id)
    if dataset is None:
        raise ValueError("更新対象のデータが見つかりません。")
    if dataset["source_type"] == "postgresql_query":
        return refresh_postgresql_dataset(conn, dataset_id)
    if dataset["source_type"] == "mysql_query":
        return refresh_mysql_dataset(conn, dataset_id)
    raise ValueError("このデータはDB更新に対応していません。")


def get_relations(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            r.id,
            r.left_dataset_id,
            r.left_field_id,
            r.right_dataset_id,
            r.right_field_id,
            r.created_at,
            ld.name AS left_dataset_name,
            lf.display_name AS left_field_name,
            rd.name AS right_dataset_name,
            rf.display_name AS right_field_name
        FROM relations r
        JOIN datasets ld ON ld.id = r.left_dataset_id
        JOIN dataset_fields lf ON lf.id = r.left_field_id
        JOIN datasets rd ON rd.id = r.right_dataset_id
        JOIN dataset_fields rf ON rf.id = r.right_field_id
        ORDER BY r.id DESC
        """
    )
    return cursor.fetchall()


def create_relation(conn, left_field_id, right_field_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, dataset_id FROM dataset_fields WHERE id IN (?, ?)",
        (left_field_id, right_field_id),
    )
    rows = cursor.fetchall()
    if len(rows) != 2:
        raise ValueError("関連付け対象の列が見つかりません。")
    left_dataset_id = rows[0]["dataset_id"]
    right_dataset_id = rows[1]["dataset_id"]
    if left_dataset_id == right_dataset_id:
        raise ValueError("同じデータセット内の列同士は関連付けできません。")
    cursor.execute(
        """
        SELECT id FROM relations
        WHERE left_field_id = ? AND right_field_id = ?
        """,
        (left_field_id, right_field_id),
    )
    if cursor.fetchone() is not None:
        raise ValueError("同じ関連付けは既に登録されています。")
    cursor.execute(
        """
        INSERT INTO relations (left_dataset_id, left_field_id, right_dataset_id, right_field_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (left_dataset_id, left_field_id, right_dataset_id, right_field_id, now_str()),
    )
    conn.commit()


def create_relations_bulk(conn, relation_pairs):
    created_count = 0
    for left_field_id, right_field_id in relation_pairs:
        try:
            create_relation(conn, left_field_id, right_field_id)
            created_count += 1
        except ValueError as exc:
            if str(exc) == "同じ関連付けは既に登録されています。":
                continue
            raise
    return created_count


def delete_relation(conn, relation_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM link_template_relations WHERE relation_id = ?", (relation_id,))
    cursor.execute("DELETE FROM relations WHERE id = ?", (relation_id,))
    conn.commit()


def get_templates(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.id, t.name, t.created_at, COUNT(tr.id) AS relation_count
        FROM link_templates t
        LEFT JOIN link_template_relations tr ON tr.template_id = t.id
        GROUP BY t.id, t.name, t.created_at
        ORDER BY t.id DESC
        """
    )
    return cursor.fetchall()


def get_template(conn, template_id):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.id, t.name, t.created_at, COUNT(tr.id) AS relation_count
        FROM link_templates t
        LEFT JOIN link_template_relations tr ON tr.template_id = t.id
        WHERE t.id = ?
        GROUP BY t.id, t.name, t.created_at
        """,
        (template_id,),
    )
    return cursor.fetchone()


def create_template(conn, template_name, relation_pairs):
    if not relation_pairs:
        raise ValueError("テンプレートに含める関連付けを1件以上追加してください。")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO link_templates (name, created_at) VALUES (?, ?)",
        (template_name, now_str()),
    )
    template_id = cursor.lastrowid
    for order, relation_pair in enumerate(relation_pairs):
        left_field_id, right_field_id = relation_pair
        cursor.execute(
            "INSERT INTO link_template_relations (template_id, relation_id, left_field_id, right_field_id, sort_order) VALUES (?, ?, ?, ?, ?)",
            (template_id, 0, left_field_id, right_field_id, order),
        )
    conn.commit()


def update_template(conn, template_id, template_name, relation_pairs):
    if not relation_pairs:
        raise ValueError("テンプレートに含める関連付けを1件以上追加してください。")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM link_templates WHERE id = ?", (template_id,))
    if cursor.fetchone() is None:
        raise ValueError("編集対象のテンプレートが見つかりません。")
    cursor.execute(
        "UPDATE link_templates SET name = ? WHERE id = ?",
        (template_name, template_id),
    )
    cursor.execute("DELETE FROM link_template_relations WHERE template_id = ?", (template_id,))
    for order, relation_pair in enumerate(relation_pairs):
        left_field_id, right_field_id = relation_pair
        cursor.execute(
            "INSERT INTO link_template_relations (template_id, relation_id, left_field_id, right_field_id, sort_order) VALUES (?, ?, ?, ?, ?)",
            (template_id, 0, left_field_id, right_field_id, order),
        )
    conn.commit()


def delete_template(conn, template_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM link_template_relations WHERE template_id = ?", (template_id,))
    cursor.execute("DELETE FROM link_templates WHERE id = ?", (template_id,))
    conn.commit()


def get_template_relations(conn, template_id):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            tr.sort_order,
            COALESCE(r.id, 0) AS id,
            ldf.dataset_id AS left_dataset_id,
            COALESCE(tr.left_field_id, r.left_field_id) AS left_field_id,
            rdf.dataset_id AS right_dataset_id,
            COALESCE(tr.right_field_id, r.right_field_id) AS right_field_id,
            ld.name AS left_dataset_name,
            lf.display_name AS left_field_name,
            rd.name AS right_dataset_name,
            rf.display_name AS right_field_name,
            ld.table_name AS left_table_name,
            rd.table_name AS right_table_name,
            lf.field_key AS left_field_key,
            rf.field_key AS right_field_key
        FROM link_template_relations tr
        LEFT JOIN relations r ON r.id = tr.relation_id
        JOIN dataset_fields lf ON lf.id = COALESCE(tr.left_field_id, r.left_field_id)
        JOIN dataset_fields rf ON rf.id = COALESCE(tr.right_field_id, r.right_field_id)
        JOIN dataset_fields ldf ON ldf.id = lf.id
        JOIN dataset_fields rdf ON rdf.id = rf.id
        JOIN datasets ld ON ld.id = ldf.dataset_id
        JOIN datasets rd ON rd.id = rdf.dataset_id
        WHERE tr.template_id = ?
        ORDER BY tr.sort_order ASC, tr.id ASC
        """,
        (template_id,),
    )
    return cursor.fetchall()


def parse_relation_pairs(pending_relations_raw):
    try:
        pending_relations = json.loads(pending_relations_raw)
    except ValueError:
        pending_relations = []
    relation_pairs = []
    for item in pending_relations:
        if not isinstance(item, dict):
            continue
        left_field_id = int(item.get("leftFieldId", 0) or 0)
        right_field_id = int(item.get("rightFieldId", 0) or 0)
        if left_field_id and right_field_id:
            relation_pairs.append((left_field_id, right_field_id))
    unique_relation_pairs = []
    seen_relation_pairs = set()
    for relation_pair in relation_pairs:
        if relation_pair in seen_relation_pairs:
            continue
        seen_relation_pairs.add(relation_pair)
        unique_relation_pairs.append(relation_pair)
    return unique_relation_pairs


def export_template_csv(conn, template_id):
    relations = get_template_relations(conn, template_id)
    if not relations:
        raise ValueError("テンプレートに関連付けがありません。")

    first = relations[0]
    base_dataset_id = first["left_dataset_id"]
    aliases = {base_dataset_id: "d0"}
    dataset_order = [base_dataset_id]
    join_clauses = []

    for relation in relations:
        left_dataset_id = relation["left_dataset_id"]
        right_dataset_id = relation["right_dataset_id"]
        if left_dataset_id not in aliases:
            aliases[left_dataset_id] = "d{0}".format(len(aliases))
            dataset_order.append(left_dataset_id)
        if right_dataset_id not in aliases:
            aliases[right_dataset_id] = "d{0}".format(len(aliases))
            dataset_order.append(right_dataset_id)
            join_clauses.append(
                "LEFT JOIN {right_table} {right_alias} ON {left_alias}.{left_field} = {right_alias}.{right_field}".format(
                    right_table=quote_identifier(relation["right_table_name"]),
                    right_alias=aliases[right_dataset_id],
                    left_alias=aliases[left_dataset_id],
                    left_field=quote_identifier(relation["left_field_key"]),
                    right_field=quote_identifier(relation["right_field_key"]),
                )
            )

    fields = get_dataset_fields(conn)
    fields_by_dataset = {}
    for field in fields:
        fields_by_dataset.setdefault(field["dataset_id"], []).append(field)

    select_parts = []
    headers = []
    for dataset_id in dataset_order:
        alias = aliases[dataset_id]
        dataset_fields = fields_by_dataset.get(dataset_id, [])
        for field in dataset_fields:
            select_parts.append(
                "{alias}.{field_key} AS {result_key}".format(
                    alias=alias,
                    field_key=quote_identifier(field["field_key"]),
                    result_key=quote_identifier("{0}__{1}".format(dataset_id, field["field_key"])),
                )
            )
            headers.append("{0}:{1}".format(field["dataset_id"], field["display_name"]))

    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM datasets WHERE id = ?", (base_dataset_id,))
    base_table_name = cursor.fetchone()[0]
    sql = "SELECT {0} FROM {1} {2} {3}".format(
        ", ".join(select_parts),
        quote_identifier(base_table_name),
        aliases[base_dataset_id],
        " ".join(join_clauses),
    )
    cursor.execute(sql)
    rows = cursor.fetchall()

    template_name = "template_{0}".format(template_id)
    cursor.execute("SELECT name FROM link_templates WHERE id = ?", (template_id,))
    template_row = cursor.fetchone()
    if template_row is not None:
        template_name = template_row[0]
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in template_name) or "export"
    export_filename = "{0}_{1}.csv".format(safe_name, datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    export_path = os.path.join(EXPORT_DIR, export_filename)
    with open(export_path, "w", encoding="utf-8-sig", newline="") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(list(row))
    return export_filename, len(rows)


def render_header(title):
    print("Content-Type: text/html; charset=utf-8\n")
    print("<!DOCTYPE html>")
    print("<html lang=\"ja\">")
    print("<head>")
    print("<meta charset=\"utf-8\">")
    print("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
    print("<title>{0}</title>".format(html_escape(title)))
    print("<link rel=\"stylesheet\" href=\"?asset=app.css\">")
    print("</head>")
    print("<body>")


def render_footer(extra_script=False):
    if extra_script:
        print("<script src=\"?asset=app.js\"></script>")
    print("</body>")
    print("</html>")


def render_navigation(page):
    pages = [
        ("upload", "データアップロード"),
        ("relations", "データ連携"),
    ]
    print("<header class=\"hero\">")
    print("<div class=\"hero-inner\">")
    print("<div><h1>データ組み合わせツール</h1><p>CSVやDBクエリ結果を取り込み、列同士の関係を定義し、テンプレートとして再利用できます。</p></div>")
    print("<nav class=\"tabs\">")
    for key, label in pages:
        class_name = "tab is-active" if key == page else "tab"
        print("<a class=\"{0}\" href=\"?page={1}\">{2}</a>".format(class_name, key, html_escape(label)))
    print("</nav>")
    print("</div>")
    print("</header>")


def render_flash(message, level="info"):
    if not message:
        return
    print("<div class=\"flash flash-{0}\">{1}</div>".format(level, html_escape(message)))


def render_upload_page(conn, message="", level="info"):
    datasets = get_datasets(conn)
    fields = get_dataset_fields(conn)
    samples = get_dataset_samples(conn)
    fields_by_dataset = {}
    for field in fields:
        fields_by_dataset.setdefault(field["dataset_id"], []).append(field)

    render_header("データアップロード")
    render_navigation("upload")
    print("<main class=\"layout\">")
    render_flash(message, level)
    print("<section class=\"panel\">")
    print("<h2>CSVアップロード</h2>")
    print("<form method=\"post\" enctype=\"multipart/form-data\" class=\"stack\">")
    print("<input type=\"hidden\" name=\"action\" value=\"upload_dataset\">")
    print("<label>表示名<input type=\"text\" name=\"dataset_name\" required></label>")
    print("<label>CSVファイル<input type=\"file\" name=\"csv_file\" accept=\".csv\" required></label>")
    print("<button class=\"btn primary\" type=\"submit\">取り込む</button>")
    print("</form>")
    print("</section>")

    print("<section class=\"panel\">")
    print("<h2>DBクエリ取り込み</h2>")
    print("<form method=\"post\" class=\"stack\">")
    print("<input type=\"hidden\" name=\"action\" value=\"register_db_dataset\">")
    print("<div class=\"two-col\">")
    print("<label>DB種別<select name=\"db_type\"><option value=\"mysql\">MySQL</option><option value=\"postgresql\">PostgreSQL</option></select></label>")
    print("<label>表示名<input type=\"text\" name=\"dataset_name\" required></label>")
    print("</div>")
    print("<div class=\"two-col\">")
    print("<label>ホスト<input type=\"text\" name=\"db_host\" value=\"localhost\" required></label>")
    print("<label>ポート<input type=\"text\" name=\"db_port\" value=\"\"></label>")
    print("</div>")
    print("<div class=\"two-col\">")
    print("<label>データベース名<input type=\"text\" name=\"db_name\" required></label>")
    print("<label>ユーザー名<input type=\"text\" name=\"db_user\" required></label>")
    print("</div>")
    print("<label>パスワード<input type=\"password\" name=\"db_password\"></label>")
    print("<label>取得クエリ<textarea name=\"db_query\" required></textarea></label>")
    print("<p class=\"helper-text\">MySQL と PostgreSQL に対応しています。ポート未入力時は MySQL=3306、PostgreSQL=5432 を使用します。登録後は更新ボタンで同じ接続先・クエリから再取得できます。</p>")
    print("<button class=\"btn primary\" type=\"submit\">DBから取り込む</button>")
    print("</form>")
    print("</section>")

    print("<section class=\"panel\">")
    print("<div class=\"panel-head\"><h2>登録済みデータ</h2><span>{0} 件</span></div>".format(len(datasets)))
    if not datasets:
        print("<p class=\"empty\">まだデータは登録されていません。</p>")
    for dataset in datasets:
        dataset_id = dataset["id"]
        dataset_fields = fields_by_dataset.get(dataset_id, [])
        sample_rows = samples.get(dataset_id, [])
        source_type = dataset["source_type"] or "csv"
        source_config = parse_source_config_text(dataset["source_config"])
        source_label = dataset["original_filename"]
        if source_type == "mysql_query":
            source_label = "MySQL / {0}".format(format_mysql_source_label(source_config))
        elif source_type == "postgresql_query":
            source_label = "PostgreSQL / {0}".format(format_postgresql_source_label(source_config))
        print("<article class=\"dataset-card\">")
        print("<div class=\"dataset-card-head\">")
        print("<div>")
        print("<h3>{0}</h3>".format(html_escape(dataset["name"])))
        print("<p>{0} / {1} 行 / {2}</p>".format(
            html_escape(source_label),
            dataset["row_count"],
            html_escape(dataset["encoding"]),
        ))
        if source_type in ("mysql_query", "postgresql_query"):
            print("<p class=\"helper-text\">最終更新: {0}</p>".format(html_escape(dataset["last_refreshed_at"] or dataset["created_at"])))
        print("</div>")
        print("<div class=\"dataset-actions\">")
        if source_type in ("mysql_query", "postgresql_query"):
            print("<form method=\"post\" class=\"inline-form\">")
            print("<input type=\"hidden\" name=\"action\" value=\"refresh_db_dataset\">")
            print("<input type=\"hidden\" name=\"dataset_id\" value=\"{0}\">".format(dataset_id))
            print("<button class=\"btn\" type=\"submit\">更新</button>")
            print("</form>")
        print("<form method=\"post\" class=\"inline-form\">")
        print("<input type=\"hidden\" name=\"action\" value=\"rename_dataset\">")
        print("<input type=\"hidden\" name=\"dataset_id\" value=\"{0}\">".format(dataset_id))
        print("<input type=\"text\" name=\"new_name\" value=\"{0}\" required>".format(html_escape(dataset["name"])))
        print("<button class=\"btn\" type=\"submit\">名前変更</button>")
        print("</form>")
        print("<form method=\"post\" class=\"inline-form\" onsubmit=\"return confirm('このデータを削除しますか？');\">")
        print("<input type=\"hidden\" name=\"action\" value=\"delete_dataset\">")
        print("<input type=\"hidden\" name=\"dataset_id\" value=\"{0}\">".format(dataset_id))
        print("<button class=\"btn danger\" type=\"submit\">削除</button>")
        print("</form>")
        print("</div>")
        print("</div>")
        print("<div class=\"field-list\">")
        for field in dataset_fields:
            print("<span class=\"field-chip\">{0}</span>".format(html_escape(field["display_name"])))
        print("</div>")
        if sample_rows:
            print("<div class=\"dataset-preview-meta\">先頭 {0} 行を表示 / 全 {1} 行</div>".format(len(sample_rows), dataset["row_count"]))
            print("<div class=\"table-wrap\"><table><thead><tr>")
            for field in dataset_fields:
                print("<th>{0}</th>".format(html_escape(field["display_name"])))
            print("</tr></thead><tbody>")
            for sample_row in sample_rows:
                print("<tr>")
                for field in dataset_fields:
                    print("<td>{0}</td>".format(html_escape(sample_row[field["field_key"]])))
                print("</tr>")
            print("</tbody></table></div>")
        else:
            print("<div class=\"dataset-preview-meta\">データ行はありません。</div>")
        print("</article>")
    print("</section>")
    print("</main>")
    render_footer(False)


def render_relation_page(conn, message="", level="info", edit_template_id=0):
    datasets = get_datasets(conn)
    fields = get_dataset_fields(conn)
    relations = get_relations(conn)
    templates = get_templates(conn)
    editing_template = None
    editing_relations = []
    if edit_template_id:
        editing_template = get_template(conn, edit_template_id)
        if editing_template is not None:
            editing_relations = get_template_relations(conn, edit_template_id)

    fields_by_dataset = {}
    for field in fields:
        fields_by_dataset.setdefault(field["dataset_id"], []).append(field)

    render_header("データ連携")
    render_navigation("relations")
    print("<main class=\"layout\">")
    render_flash(message, level)

    print("<section class=\"panel\">")
    print("<div class=\"panel-head\"><h2>ノードベース連携</h2><span>ヘッダーで移動 / 項目をドラッグして接続</span></div>")
    print("<div class=\"builder\">")
    print("<aside class=\"builder-side\">")
    print("<form method=\"post\" id=\"relation-form\" class=\"stack\">")
    print("<input type=\"hidden\" name=\"action\" value=\"create_relations_bulk\">")
    print("<input type=\"hidden\" name=\"pending_relations\" id=\"pending-relations\" value=\"[]\">")
    print("<p class=\"helper-text\">項目をドラッグして別ノードの項目へドロップすると、未保存一覧へ追加されます。</p>")
    print("<div class=\"pending-box\">")
    print("<div class=\"pending-head\"><strong>未保存の関連付け</strong><button class=\"btn danger\" type=\"button\" id=\"clear-pending-btn\">クリア</button></div>")
    print("<div id=\"pending-relations-empty\" class=\"empty\">未保存の関連付けはありません。</div>")
    print("<div id=\"pending-relations-list\" class=\"pending-list\"></div>")
    print("</div>")
    print("<button class=\"btn primary\" type=\"submit\" id=\"save-pending-btn\">まとめて保存</button>")
    print("</form>")
    print("<form method=\"post\" class=\"stack\" id=\"template-form\">")
    print("<input type=\"hidden\" name=\"action\" value=\"{0}\">".format("update_template" if editing_template else "save_template"))
    if editing_template is not None:
        print("<input type=\"hidden\" name=\"template_id\" value=\"{0}\">".format(editing_template["id"]))
    print("<input type=\"hidden\" name=\"pending_relations\" id=\"template-pending-relations\" value=\"[]\">")
    print("<label>テンプレート名<input type=\"text\" name=\"template_name\" value=\"{0}\" required></label>".format(html_escape(editing_template["name"]) if editing_template is not None else ""))
    print("<p class=\"helper-text\">{0}</p>".format("未保存一覧の関連付けでテンプレート内容を更新します。" if editing_template is not None else "未保存一覧の関連付けを、そのままテンプレートの関連付けとして保存します。"))
    print("<div class=\"template-form-actions\">")
    print("<button class=\"btn\" type=\"submit\">{0}</button>".format("テンプレート更新" if editing_template is not None else "テンプレート保存"))
    if editing_template is not None:
        print("<a class=\"btn\" href=\"?page=relations\">編集をキャンセル</a>")
    print("</div>")
    print("</form>")
    print("</aside>")

    print("<div class=\"builder-main\">")
    print("<div class=\"builder-toolbar\">")
    print("<span class=\"helper-text\">ホイールまたはボタンで表示倍率を変更できます。</span>")
    print("<div class=\"zoom-controls\">")
    print("<button class=\"btn\" type=\"button\" id=\"zoom-out-btn\">-</button>")
    print("<button class=\"btn\" type=\"button\" id=\"zoom-reset-btn\">100%</button>")
    print("<button class=\"btn\" type=\"button\" id=\"zoom-in-btn\">+</button>")
    print("<span class=\"zoom-status\" id=\"zoom-status\">100%</span>")
    print("</div>")
    print("</div>")
    print("<div class=\"dataset-palette\">")
    print("<div class=\"panel-head\"><h3>利用可能なデータテーブル</h3><span>ドラッグして追加</span></div>")
    print("<div class=\"dataset-palette-list\" id=\"dataset-palette-list\">")
    for dataset in datasets:
        print(
            "<button type=\"button\" class=\"dataset-chip\" draggable=\"true\" data-dataset-source-id=\"{0}\">{1}</button>".format(
                dataset["id"],
                html_escape(dataset["name"]),
            )
        )
    print("</div>")
    print("</div>")
    print("<div class=\"builder-canvas\" id=\"relation-canvas\">")
    print("<div class=\"builder-stage\" id=\"relation-stage\">")
    print("<svg class=\"relation-svg\" id=\"relation-svg\"></svg>")
    x_positions = [40, 420, 800]
    for index, dataset in enumerate(datasets):
        left = x_positions[index % len(x_positions)]
        top = 24 + (index // len(x_positions)) * 340
        print("<section class=\"node is-hidden\" data-dataset-id=\"{0}\" data-default-left=\"{1}\" data-default-top=\"{2}\" style=\"left:{1}px;top:{2}px\">".format(dataset["id"], left, top))
        print("<header class=\"node-header\"><span>{0}</span><span class=\"node-header-actions\"><button type=\"button\" class=\"node-remove-btn\" data-remove-dataset-id=\"{1}\">外す</button><span class=\"node-handle\">移動</span></span></header>".format(html_escape(dataset["name"]), dataset["id"]))
        print("<div class=\"node-body\">")
        for field in fields_by_dataset.get(dataset["id"], []):
            label = "{0}.{1}".format(dataset["name"], field["display_name"])
            print(
                "<button type=\"button\" class=\"field-pin\" draggable=\"true\" data-dataset-id=\"{0}\" data-field-id=\"{1}\" data-label=\"{2}\">{3}</button>".format(
                    dataset["id"],
                    field["id"],
                    html_escape(label),
                    html_escape(field["display_name"]),
                )
            )
        print("</div></section>")
    print("</div>")
    print("</div>")
    if relations:
        print("<div class=\"table-wrap\"><table><thead><tr><th>ID</th><th>関連</th><th>操作</th></tr></thead><tbody>")
        for relation in relations:
            print("<tr>")
            print("<td>{0}</td>".format(relation["id"]))
            print("<td>{0}.{1} → {2}.{3}</td>".format(
                html_escape(relation["left_dataset_name"]),
                html_escape(relation["left_field_name"]),
                html_escape(relation["right_dataset_name"]),
                html_escape(relation["right_field_name"]),
            ))
            print("<td>")
            print("<form method=\"post\" onsubmit=\"return confirm('この関連付けを削除しますか？');\">")
            print("<input type=\"hidden\" name=\"action\" value=\"delete_relation\">")
            print("<input type=\"hidden\" name=\"relation_id\" value=\"{0}\">".format(relation["id"]))
            print("<button class=\"btn danger\" type=\"submit\">削除</button>")
            print("</form>")
            print("</td>")
            print("</tr>")
        print("</tbody></table></div>")
    else:
        print("<p class=\"empty\">関連付けはまだありません。</p>")
    print("</div>")

    print("<div>")
    print("<div class=\"panel-head\"><h2>テンプレート</h2><span>{0} 件</span></div>".format(len(templates)))
    if templates:
        print("<div class=\"template-list\">")
        for template in templates:
            print("<article class=\"template-card\">")
            print("<h3>{0}</h3>".format(html_escape(template["name"])))
            print("<p>{0} 件の関連付け / {1}</p>".format(template["relation_count"], html_escape(template["created_at"])))
            print("<div class=\"template-actions\">")
            print("<a class=\"btn\" href=\"?page=relations&edit_template_id={0}\">編集</a>".format(template["id"]))
            print("<form method=\"post\">")
            print("<input type=\"hidden\" name=\"action\" value=\"export_template\">")
            print("<input type=\"hidden\" name=\"template_id\" value=\"{0}\">".format(template["id"]))
            print("<button class=\"btn primary\" type=\"submit\">CSV出力</button>")
            print("</form>")
            print("<form method=\"post\" onsubmit=\"return confirm('このテンプレートを削除しますか？');\">\n")
            print("<input type=\"hidden\" name=\"action\" value=\"delete_template\">")
            print("<input type=\"hidden\" name=\"template_id\" value=\"{0}\">".format(template["id"]))
            print("<button class=\"btn danger\" type=\"submit\">削除</button>")
            print("</form>")
            print("</div>")
            print("</article>")
        print("</div>")
    else:
        print("<p class=\"empty\">テンプレートはまだありません。</p>")
    print("</div>")
    print("</section>")

    relation_json = []
    for relation in relations:
        relation_json.append({
            "leftFieldId": relation["left_field_id"],
            "rightFieldId": relation["right_field_id"],
        })
    relation_json_text = json.dumps(relation_json).replace("</", "<\\/")
    editing_relation_json = []
    for relation in editing_relations:
        editing_relation_json.append({
            "leftFieldId": str(relation["left_field_id"]),
            "rightFieldId": str(relation["right_field_id"]),
            "leftLabel": "{0}.{1}".format(relation["left_dataset_name"], relation["left_field_name"]),
            "rightLabel": "{0}.{1}".format(relation["right_dataset_name"], relation["right_field_name"]),
        })
    editing_relation_json_text = json.dumps(editing_relation_json).replace("</", "<\\/")
    print("<script id=\"relation-data\" type=\"application/json\">{0}</script>".format(relation_json_text))
    print("<script id=\"editing-template-relations\" type=\"application/json\">{0}</script>".format(editing_relation_json_text))
    print("</main>")
    render_footer(True)


def serve_asset(asset_name):
    if asset_name not in STATIC_FILES:
        raise ValueError("指定されたアセットは存在しません。")
    content_type, filename = STATIC_FILES[asset_name]
    file_path = os.path.join(BASE_DIR, filename)
    with open(file_path, "r", encoding="utf-8") as file_handle:
        content = file_handle.read()
    print("Content-Type: {0}\n".format(content_type))
    print(content)


def render_error(message):
    render_header("エラー")
    print("<main class=\"layout\"><section class=\"panel\"><h2>エラー</h2><p>{0}</p></section></main>".format(html_escape(message)))
    render_footer(False)


def handle_post(conn, form):
    action = form.getfirst("action", "")
    if action == "upload_dataset":
        file_item = form["csv_file"] if "csv_file" in form else None
        dataset_name = form.getfirst("dataset_name", "").strip()
        if not dataset_name:
            raise ValueError("表示名を入力してください。")
        if file_item is None or not getattr(file_item, "filename", ""):
            raise ValueError("CSVファイルを選択してください。")
        encoding, headers, data_rows = load_csv_rows(file_item)
        create_dataset(conn, dataset_name, os.path.basename(file_item.filename), encoding, headers, data_rows)
        return "upload", "データを取り込みました。", "success"

    if action == "register_db_dataset":
        dataset_name = form.getfirst("dataset_name", "").strip()
        query_text = form.getfirst("db_query", "")
        if not dataset_name:
            raise ValueError("表示名を入力してください。")
        source_config = parse_db_source_form(form)
        row_count = register_db_dataset(conn, dataset_name, source_config, query_text)
        return "upload", "DBからデータを取り込みました。{0} 行取得しました。".format(row_count), "success"

    if action == "rename_dataset":
        dataset_id = int(form.getfirst("dataset_id", "0"))
        new_name = form.getfirst("new_name", "").strip()
        if not new_name:
            raise ValueError("新しい名前を入力してください。")
        rename_dataset(conn, dataset_id, new_name)
        return "upload", "データ名を更新しました。", "success"

    if action == "delete_dataset":
        dataset_id = int(form.getfirst("dataset_id", "0"))
        delete_dataset(conn, dataset_id)
        return "upload", "データを削除しました。", "success"

    if action == "refresh_db_dataset":
        dataset_id = int(form.getfirst("dataset_id", "0"))
        row_count = refresh_db_dataset(conn, dataset_id)
        return "upload", "DBデータを更新しました。{0} 行取得しました。".format(row_count), "success"

    if action == "create_relation":
        left_field_id = int(form.getfirst("left_field_id", "0"))
        right_field_id = int(form.getfirst("right_field_id", "0"))
        if not left_field_id or not right_field_id:
            raise ValueError("左右の列を選択してください。")
        create_relation(conn, left_field_id, right_field_id)
        return "relations", "関連付けを保存しました。", "success"

    if action == "create_relations_bulk":
        pending_relations_raw = form.getfirst("pending_relations", "[]")
        try:
            pending_relations = json.loads(pending_relations_raw)
        except ValueError:
            pending_relations = []
        relation_pairs = []
        for item in pending_relations:
            if not isinstance(item, dict):
                continue
            left_field_id = int(item.get("leftFieldId", 0) or 0)
            right_field_id = int(item.get("rightFieldId", 0) or 0)
            if left_field_id and right_field_id:
                relation_pairs.append((left_field_id, right_field_id))
        if not relation_pairs:
            raise ValueError("保存する未保存の関連付けがありません。")
        created_count = create_relations_bulk(conn, relation_pairs)
        return "relations", "関連付けをまとめて保存しました。{0} 件追加しました。".format(created_count), "success"

    if action == "delete_relation":
        relation_id = int(form.getfirst("relation_id", "0"))
        delete_relation(conn, relation_id)
        return "relations", "関連付けを削除しました。", "success"

    if action == "save_template":
        template_name = form.getfirst("template_name", "").strip()
        pending_relations_raw = form.getfirst("pending_relations", "[]")
        if not template_name:
            raise ValueError("テンプレート名を入力してください。")
        create_template(conn, template_name, parse_relation_pairs(pending_relations_raw))
        return "relations", "テンプレートを保存しました。", "success"

    if action == "update_template":
        template_id = int(form.getfirst("template_id", "0"))
        template_name = form.getfirst("template_name", "").strip()
        pending_relations_raw = form.getfirst("pending_relations", "[]")
        if not template_name:
            raise ValueError("テンプレート名を入力してください。")
        update_template(conn, template_id, template_name, parse_relation_pairs(pending_relations_raw))
        return "relations", "テンプレートを更新しました。", "success"

    if action == "delete_template":
        template_id = int(form.getfirst("template_id", "0"))
        delete_template(conn, template_id)
        return "relations", "テンプレートを削除しました。", "success"

    if action == "export_template":
        template_id = int(form.getfirst("template_id", "0"))
        export_filename, row_count = export_template_csv(conn, template_id)
        return "relations", "CSVを出力しました: {0} ({1} 行)".format(export_filename, row_count), "success"

    raise ValueError("未対応の操作です。")


def main():
    ensure_dirs()
    conn = get_connection()
    init_db(conn)
    seed_samples_if_needed(conn)
    form = parse_form()
    page = form.getfirst("page", "upload")
    asset = form.getfirst("asset", "")
    message = ""
    level = "info"
    try:
        if asset:
            serve_asset(asset)
            return
        if os.environ.get("REQUEST_METHOD", "GET").upper() == "POST":
            page, message, level = handle_post(conn, form)
        edit_template_id = int(form.getfirst("edit_template_id", "0") or 0)
        if page == "relations":
            render_relation_page(conn, message, level, edit_template_id)
        else:
            render_upload_page(conn, message, level)
    finally:
        conn.close()


def run():
    configure_output()
    setup_cgitb()
    try:
        main()
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        render_error(str(exc))


if __name__ == "__main__":
    run()
