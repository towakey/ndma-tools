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

import cgi
import cgitb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
STATIC_FILES = {
    "app.css": ("text/css; charset=utf-8", "app.css"),
    "app.js": ("application/javascript; charset=utf-8", "app.js"),
}


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
            created_at TEXT NOT NULL
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
            sort_order INTEGER NOT NULL,
            FOREIGN KEY(template_id) REFERENCES link_templates(id),
            FOREIGN KEY(relation_id) REFERENCES relations(id)
        )
        """
    )
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


def detect_encoding(raw_bytes):
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            raw_bytes.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("CSVの文字コードを判定できませんでした。UTF-8 または CP932 を使用してください。")


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
    headers = [value.strip() or "列{0}".format(index + 1) for index, value in enumerate(rows[0])]
    data_rows = rows[1:]
    return encoding, headers, data_rows


def create_dataset(conn, dataset_name, original_filename, encoding, headers, data_rows):
    cursor = conn.cursor()
    table_name = next_table_name(conn)
    created_at = now_str()
    row_count = len(data_rows)
    cursor.execute(
        """
        INSERT INTO datasets (name, original_filename, table_name, encoding, row_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (dataset_name, original_filename, table_name, encoding, row_count, created_at),
    )
    dataset_id = cursor.lastrowid

    field_keys = []
    for index, header in enumerate(headers):
        field_key = "col_{0:03d}".format(index + 1)
        field_keys.append(field_key)
        cursor.execute(
            """
            INSERT INTO dataset_fields (dataset_id, field_key, original_name, display_name, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (dataset_id, field_key, header, header, index),
        )

    create_table_sql = "CREATE TABLE {0} (row_id INTEGER PRIMARY KEY AUTOINCREMENT".format(
        quote_identifier(table_name)
    )
    for field_key in field_keys:
        create_table_sql += ", {0} TEXT".format(quote_identifier(field_key))
    create_table_sql += ")"
    cursor.execute(create_table_sql)

    if data_rows:
        placeholders = ", ".join(["?"] * len(field_keys))
        insert_sql = "INSERT INTO {0} ({1}) VALUES ({2})".format(
            quote_identifier(table_name),
            ", ".join(quote_identifier(field_key) for field_key in field_keys),
            placeholders,
        )
        normalized_rows = []
        width = len(field_keys)
        for row in data_rows:
            values = list(row[:width])
            while len(values) < width:
                values.append("")
            normalized_rows.append(values)
        cursor.executemany(insert_sql, normalized_rows)
    conn.commit()


def get_datasets(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, original_filename, table_name, encoding, row_count, created_at
        FROM datasets
        ORDER BY created_at DESC, id DESC
        """
    )
    return cursor.fetchall()


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


def get_dataset_samples(conn, limit_per_dataset=5):
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
    cursor.execute("DELETE FROM relations WHERE left_dataset_id = ? OR right_dataset_id = ?", (dataset_id, dataset_id))
    cursor.execute("DELETE FROM dataset_fields WHERE dataset_id = ?", (dataset_id,))
    cursor.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
    cursor.execute("DROP TABLE IF EXISTS {0}".format(quote_identifier(table_name)))
    conn.commit()


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


def create_template(conn, template_name, relation_ids):
    if not relation_ids:
        raise ValueError("テンプレートに含める関連付けを1件以上選択してください。")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO link_templates (name, created_at) VALUES (?, ?)",
        (template_name, now_str()),
    )
    template_id = cursor.lastrowid
    for order, relation_id in enumerate(relation_ids):
        cursor.execute(
            "INSERT INTO link_template_relations (template_id, relation_id, sort_order) VALUES (?, ?, ?)",
            (template_id, relation_id, order),
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
            r.id,
            r.left_dataset_id,
            r.left_field_id,
            r.right_dataset_id,
            r.right_field_id,
            ld.name AS left_dataset_name,
            lf.display_name AS left_field_name,
            rd.name AS right_dataset_name,
            rf.display_name AS right_field_name,
            ld.table_name AS left_table_name,
            rd.table_name AS right_table_name,
            lf.field_key AS left_field_key,
            rf.field_key AS right_field_key
        FROM link_template_relations tr
        JOIN relations r ON r.id = tr.relation_id
        JOIN datasets ld ON ld.id = r.left_dataset_id
        JOIN datasets rd ON rd.id = r.right_dataset_id
        JOIN dataset_fields lf ON lf.id = r.left_field_id
        JOIN dataset_fields rf ON rf.id = r.right_field_id
        WHERE tr.template_id = ?
        ORDER BY tr.sort_order ASC, tr.id ASC
        """,
        (template_id,),
    )
    return cursor.fetchall()


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
    print("<div><h1>データ組み合わせツール</h1><p>CSVを取り込み、列同士の関係を定義し、テンプレートとして再利用できます。</p></div>")
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
    print("<div class=\"panel-head\"><h2>登録済みデータ</h2><span>{0} 件</span></div>".format(len(datasets)))
    if not datasets:
        print("<p class=\"empty\">まだCSVは登録されていません。</p>")
    for dataset in datasets:
        dataset_id = dataset["id"]
        dataset_fields = fields_by_dataset.get(dataset_id, [])
        sample_rows = samples.get(dataset_id, [])
        print("<article class=\"dataset-card\">")
        print("<div class=\"dataset-card-head\">")
        print("<div>")
        print("<h3>{0}</h3>".format(html_escape(dataset["name"])))
        print("<p>{0} / {1} 行 / {2}</p>".format(
            html_escape(dataset["original_filename"]),
            dataset["row_count"],
            html_escape(dataset["encoding"]),
        ))
        print("</div>")
        print("<div class=\"dataset-actions\">")
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
        print("</article>")
    print("</section>")
    print("</main>")
    render_footer(False)


def render_relation_page(conn, message="", level="info"):
    datasets = get_datasets(conn)
    fields = get_dataset_fields(conn)
    relations = get_relations(conn)
    templates = get_templates(conn)

    fields_by_dataset = {}
    for field in fields:
        fields_by_dataset.setdefault(field["dataset_id"], []).append(field)

    render_header("データ連携")
    render_navigation("relations")
    print("<main class=\"layout\">")
    render_flash(message, level)

    print("<section class=\"panel\">")
    print("<div class=\"panel-head\"><h2>ノードベース連携</h2><span>列をクリックして関連付け</span></div>")
    print("<div class=\"builder\">")
    print("<aside class=\"builder-side\">")
    print("<form method=\"post\" id=\"relation-form\" class=\"stack\">")
    print("<input type=\"hidden\" name=\"action\" value=\"create_relation\">")
    print("<input type=\"hidden\" name=\"left_field_id\" id=\"left-field-id\">")
    print("<input type=\"hidden\" name=\"right_field_id\" id=\"right-field-id\">")
    print("<label>左側の列<input type=\"text\" id=\"left-field-label\" readonly placeholder=\"未選択\"></label>")
    print("<label>右側の列<input type=\"text\" id=\"right-field-label\" readonly placeholder=\"未選択\"></label>")
    print("<button class=\"btn primary\" type=\"submit\">関連付けを保存</button>")
    print("</form>")
    print("<form method=\"post\" class=\"stack\">")
    print("<input type=\"hidden\" name=\"action\" value=\"save_template\">")
    print("<label>テンプレート名<input type=\"text\" name=\"template_name\" required></label>")
    print("<label>関連付け選択<select name=\"relation_ids\" multiple size=\"8\">")
    for relation in relations:
        label = "{0}.{1} → {2}.{3}".format(
            relation["left_dataset_name"],
            relation["left_field_name"],
            relation["right_dataset_name"],
            relation["right_field_name"],
        )
        print("<option value=\"{0}\">{1}</option>".format(relation["id"], html_escape(label)))
    print("</select></label>")
    print("<button class=\"btn\" type=\"submit\">テンプレート保存</button>")
    print("</form>")
    print("</aside>")

    print("<div class=\"builder-canvas\" id=\"relation-canvas\">")
    print("<svg class=\"relation-svg\" id=\"relation-svg\"></svg>")
    x_positions = [40, 420, 800]
    for index, dataset in enumerate(datasets):
        left = x_positions[index % len(x_positions)]
        top = 24 + (index // len(x_positions)) * 340
        print("<section class=\"node\" data-dataset-id=\"{0}\" style=\"left:{1}px;top:{2}px\">".format(dataset["id"], left, top))
        print("<header>{0}</header>".format(html_escape(dataset["name"])))
        print("<div class=\"node-body\">")
        for field in fields_by_dataset.get(dataset["id"], []):
            label = "{0}.{1}".format(dataset["name"], field["display_name"])
            print(
                "<button type=\"button\" class=\"field-pin\" data-field-id=\"{0}\" data-label=\"{1}\">{2}</button>".format(
                    field["id"],
                    html_escape(label),
                    html_escape(field["display_name"]),
                )
            )
        print("</div></section>")
    print("</div>")
    print("</div>")
    print("</section>")

    print("<section class=\"panel two-col\">")
    print("<div>")
    print("<div class=\"panel-head\"><h2>保存済み関連付け</h2><span>{0} 件</span></div>".format(len(relations)))
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
    print("<script id=\"relation-data\" type=\"application/json\">{0}</script>".format(relation_json_text))
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

    if action == "create_relation":
        left_field_id = int(form.getfirst("left_field_id", "0"))
        right_field_id = int(form.getfirst("right_field_id", "0"))
        if not left_field_id or not right_field_id:
            raise ValueError("左右の列を選択してください。")
        create_relation(conn, left_field_id, right_field_id)
        return "relations", "関連付けを保存しました。", "success"

    if action == "delete_relation":
        relation_id = int(form.getfirst("relation_id", "0"))
        delete_relation(conn, relation_id)
        return "relations", "関連付けを削除しました。", "success"

    if action == "save_template":
        template_name = form.getfirst("template_name", "").strip()
        relation_ids = form.getlist("relation_ids")
        if not template_name:
            raise ValueError("テンプレート名を入力してください。")
        create_template(conn, template_name, [int(value) for value in relation_ids])
        return "relations", "テンプレートを保存しました。", "success"

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
        if page == "relations":
            render_relation_page(conn, message, level)
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
