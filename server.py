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
    app = Flask(__name__)

    @app.route("/state", methods=["GET"])
    def state():
        data = storage.load_db(db_path)
        if data is None:
            # return empty structure rather than 404 to match dump behaviour
            return jsonify({'status_by_team': {}, 'location_by_team': {}, 'transmissions': []})
        return jsonify(data)

    return app


def main():
    parser = argparse.ArgumentParser(description="Serve SAR tracker DB as JSON via HTTP")
    parser.add_argument("--sqlite-file", default=os.environ.get('SAR_SQLITE_FILE', './logs.db'),
                        help="sqlite file location (env SAR_SQLITE_FILE)")
    parser.add_argument("--host", default='127.0.0.1')
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    app = create_app(args.sqlite_file)
    app.run(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
