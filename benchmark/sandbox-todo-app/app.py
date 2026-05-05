"""Tiny Flask TODO app used by the triforge MVP benchmark."""
from __future__ import annotations

from flask import Flask, jsonify, request

from db import add_task, get_task, init_db, list_tasks, mark_done

app = Flask(__name__)
init_db()


@app.get("/tasks")
def tasks_index():
    return jsonify(list_tasks())


@app.post("/tasks")
def tasks_create():
    body = request.get_json(force=True)
    title = body.get("title")
    if not title:
        return jsonify({"error": "title required"}), 400
    return jsonify(add_task(title)), 201


@app.get("/tasks/<int:tid>")
def tasks_show(tid: int):
    t = get_task(tid)
    if not t:
        return jsonify({"error": "not found"}), 404
    return jsonify(t)


@app.post("/tasks/<int:tid>/done")
def tasks_done(tid: int):
    if not mark_done(tid):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
