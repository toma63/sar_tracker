"""Simple Flask server exposing the current DB state as JSON.

Endpoints:
- GET /state -> returns the same JSON structure produced by `storage.dump_db_to_json`/`storage.load_db`

Configuration:
- `SAR_SQLITE_FILE` environment variable or `--sqlite-file` CLI argument to choose DB path.
"""
from pathlib import Path
import os
import json
import argparse

from flask import Flask, jsonify, abort

import storage


def create_app(db_path):
    # resolve sqlite path to absolute so relative cwd won't cause surprises
    db_path = str(Path(db_path).resolve())
    # set static_folder so Flask serves our static files under /static
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    @app.route("/state", methods=["GET"])
    def state():
        data = storage.load_db(db_path)
        if data is None:
            # return empty structure rather than 404 to match dump behaviour
            return jsonify({'status_by_team': {}, 'location_by_team': {}, 'transmissions': []})
        return jsonify(data)

    # serve the single-page frontend at /
    @app.route('/')
    def index():
        # serve static/index.html
        return app.send_static_file('index.html')

    @app.route('/debug')
    def debug_info():
        # return basic diagnostics: which DB file we're using and counts
        try:
            data = storage.load_db(db_path)
        except Exception as e:
            return jsonify({'db_path': db_path, 'error': str(e)}), 500
        if data is None:
            return jsonify({'db_path': db_path, 'status_by_team': 0, 'transmissions': 0})
        status_count = len(data.get('status_by_team', {}) or {})
        tx_count = len(data.get('transmissions', []) or [])
        return jsonify({'db_path': db_path, 'status_by_team': status_count, 'transmissions': tx_count})

    return app


def main():
    parser = argparse.ArgumentParser(description="Serve SAR tracker DB as JSON via HTTP")
    parser.add_argument("--sqlite-file", default=os.environ.get('SAR_SQLITE_FILE', './logs.db'),
                        help="sqlite file location (env SAR_SQLITE_FILE)")
    parser.add_argument("--host", default='127.0.0.1')
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    # resolve sqlite path to absolute to avoid creating DBs in unexpected CWDs
    args.sqlite_file = str(Path(args.sqlite_file).resolve())
    print(f"Serving DB file: {args.sqlite_file}")
    app = create_app(args.sqlite_file)
    app.run(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
