import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path


def init_db(db_path):
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    cur = conn.cursor()
    # team_status stores a JSON array of status entries plus current fields
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS team_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            status_history TEXT,
            current_status TEXT,
            current_location TEXT,
            updated TIMESTAMP
        )
        """
    )
    # transmissions table for messages
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transmissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            dest TEXT,
            src TEXT,
            msg TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_db(db_path, all_logs_dict):
    """Persist the provided dictionary into the sqlite DB using two tables:

    - `team_status`: id (PK), name (UNIQUE), `status_history` (JSON text array), `current_status` (JSON text object or None), `current_location` (text)
    - `transmissions`: rows of messages

    This replaces existing contents.
    """
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # clear existing data
    cur.execute("DELETE FROM team_status")
    cur.execute("DELETE FROM transmissions")

    status_by_team = all_logs_dict.get('status_by_team', {}) or {}
    location_by_team = all_logs_dict.get('location_by_team', {}) or {}

    for name, entries in status_by_team.items():
        history_json = json.dumps(entries)
        current = entries[-1] if entries else None
        current_json = json.dumps(current) if current else None
        current_loc = current.get('location') if current and current.get('location') else location_by_team.get(name)
        # insert or update by name; keep integer id stable via ON CONFLICT DO UPDATE
        cur.execute(
            """
            INSERT INTO team_status(name, status_history, current_status, current_location, updated)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
              status_history=excluded.status_history,
              current_status=excluded.current_status,
              current_location=excluded.current_location,
              updated=excluded.updated
            """,
            (name, history_json, current_json, current_loc, datetime.now(timezone.utc).isoformat())
        )

    # ensure teams present in location_by_team but not in status_by_team
    for name, loc in location_by_team.items():
        if name not in status_by_team:
            cur.execute(
                """
                INSERT INTO team_status(name, status_history, current_status, current_location, updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                  status_history=excluded.status_history,
                  current_status=excluded.current_status,
                  current_location=excluded.current_location,
                  updated=excluded.updated
                """,
                (name, json.dumps([]), None, loc, datetime.now(timezone.utc).isoformat())
            )

    # insert transmissions
    for t in all_logs_dict.get('transmissions', []) or []:
        cur.execute(
            "INSERT INTO transmissions(timestamp, dest, src, msg) VALUES (?, ?, ?, ?)",
            (t.get('timestamp'), t.get('dest'), t.get('src'), t.get('msg'))
        )

    conn.commit()
    conn.close()


def add_status_entry(db_path, status_entry):
    """Append a single status entry (dict) to the team's history and update current columns."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    name = status_entry.get('team')

    cur.execute("SELECT status_history FROM team_status WHERE name=?", (name,))
    row = cur.fetchone()
    if row:
        try:
            history = json.loads(row[0]) if row[0] else []
        except Exception:
            history = []
        history.append(status_entry)
        history_json = json.dumps(history)
        current_json = json.dumps(status_entry)
        current_loc = status_entry.get('location')
        cur.execute(
            """
            UPDATE team_status SET
                status_history=?, current_status=?, current_location=?, updated=?
            WHERE name=?
            """,
            (history_json, current_json, current_loc, datetime.now(timezone.utc).isoformat(), name)
        )
    else:
        history_json = json.dumps([status_entry])
        current_json = json.dumps(status_entry)
        current_loc = status_entry.get('location')
        cur.execute(
            """
            INSERT INTO team_status(name, status_history, current_status, current_location, updated)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, history_json, current_json, current_loc, datetime.now(timezone.utc).isoformat())
        )

    conn.commit()
    conn.close()


def add_transmission(db_path, transmission):
    """Insert a single transmission row into the transmissions table."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO transmissions(timestamp, dest, src, msg) VALUES (?, ?, ?, ?)",
        (transmission.get('timestamp'), transmission.get('dest'), transmission.get('src'), transmission.get('msg'))
    )
    conn.commit()
    conn.close()


def load_db(db_path):
    """Load logs from sqlite DB and return a JSON-like dict compatible with the current format.
    Returns None if DB doesn't exist.
    """
    p = Path(db_path)
    if not p.exists():
        return None
    conn = sqlite3.connect(str(p))
    cur = conn.cursor()

    # load team_status rows
    cur.execute("SELECT name, status_history, current_status, current_location FROM team_status")
    rows = cur.fetchall()
    status_by_team = {}
    location_by_team = {}
    for name, status_history_text, current_status_text, current_location in rows:
        try:
            history = json.loads(status_history_text) if status_history_text else []
        except Exception:
            history = []
        status_by_team[name] = history
        # prefer current_location column if set, otherwise infer from last history entry
        if current_location:
            location_by_team[name] = current_location
        elif history and history[-1].get('location'):
            location_by_team[name] = history[-1].get('location')

    # transmissions
    cur.execute("SELECT timestamp, dest, src, msg FROM transmissions ORDER BY id")
    rows = cur.fetchall()
    transmissions = []
    for timestamp, dest, src, msg in rows:
        transmissions.append({'timestamp': timestamp, 'dest': dest, 'src': src, 'msg': msg})

    conn.close()

    return {'status_by_team': status_by_team, 'location_by_team': location_by_team, 'transmissions': transmissions}


def dump_db_to_json(db_path, json_fp):
    data = load_db(db_path)
    if data is None:
        return False
    p = Path(json_fp)
    with p.open('w') as f:
        json.dump(data, f, indent=4)
    return True


def import_json_to_db(json_fp, db_path):
    p = Path(json_fp)
    if not p.exists():
        return False
    with p.open('r') as f:
        data = json.load(f)
    save_db(db_path, data)
    return True
