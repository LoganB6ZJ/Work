"""Local center dashboard. Runs on this computer only (127.0.0.1).

  py app.py     then open http://127.0.0.1:5000
"""
import sqlite3

from flask import Flask, abort, render_template, request

import config
from timeline import center_view


def create_app(db_path=None):
    app = Flask(__name__)
    path = str(db_path or config.DB_PATH)

    def db():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    @app.route("/")
    def index():
        q = (request.args.get("q") or "").strip()
        conn = db()
        try:
            if q:
                like = f"%{q}%"
                rows = conn.execute(
                    "SELECT center_id,name,region,city,state,active FROM centers "
                    "WHERE center_id LIKE ? OR name LIKE ? OR city LIKE ? ORDER BY center_id LIMIT 300",
                    (like, like, like)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT center_id,name,region,city,state,active FROM centers ORDER BY center_id LIMIT 300").fetchall()
            total = conn.execute("SELECT COUNT(*) FROM centers").fetchone()[0]
        finally:
            conn.close()
        return render_template("index.html", rows=rows, q=q, total=total)

    @app.route("/center/<center_id>")
    def center(center_id):
        conn = db()
        try:
            info = conn.execute("SELECT * FROM centers WHERE center_id=?", (center_id,)).fetchone()
            if info is None:
                abort(404)
            view = center_view(conn, center_id)
        finally:
            conn.close()
        return render_template("center.html", c=info, v=view)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
