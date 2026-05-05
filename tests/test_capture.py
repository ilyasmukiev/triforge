from __future__ import annotations

from pathlib import Path

from triforge._config import ProjectConfig, save_project_config
from triforge._hashing import project_hash
from triforge.memory.capture import capture_from_payload
from triforge.memory.store import iter_unindexed_chats


def _activate(project: Path) -> None:
    save_project_config(project, ProjectConfig())


def test_inactive_project_is_no_op(tmp_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    payload = {
        "session_id": "s1",
        "transcript": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
    }
    n = capture_from_payload(project, payload)
    assert n == 0
    assert list(iter_unindexed_chats(project_hash(project))) == []


def test_active_project_appends_chat(tmp_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _activate(project)
    payload = {
        "session_id": "s1",
        "transcript": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
    }
    n = capture_from_payload(project, payload)
    assert n == 2
    h = project_hash(project)
    records = list(iter_unindexed_chats(h))
    assert [r.text for r in records] == ["hi", "hello"]
    assert all(r.session_id == "s1" for r in records)


def test_capture_redacts_secrets(tmp_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _activate(project)
    payload = {
        "session_id": "s1",
        "transcript": [
            {"role": "user", "content": "use OPENAI_API_KEY=sk-abc1234567890defghi"},
        ],
    }
    capture_from_payload(project, payload)
    h = project_hash(project)
    rec = next(iter_unindexed_chats(h))
    assert "sk-abc1234567890defghi" not in rec.text
    assert "[REDACTED]" in rec.text


def test_reads_transcript_path(tmp_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _activate(project)
    transcript = tmp_path / "tx.jsonl"
    transcript.write_text(
        '{"type":"user","message":{"content":[{"type":"text","text":"q1"}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"a1"}]}}\n',
        encoding="utf-8",
    )
    n = capture_from_payload(
        project,
        {"session_id": "sX", "transcript_path": str(transcript)},
    )
    assert n == 2
    texts = [r.text for r in iter_unindexed_chats(project_hash(project))]
    assert texts == ["q1", "a1"]
