from __future__ import annotations

from triforge._privacy import BUILTIN_PATTERNS, redact


def test_redacts_api_key_envvar() -> None:
    out = redact("My OPENAI_API_KEY=sk-abc123def456ghi7 is leaked")
    assert "sk-abc123def456ghi7" not in out
    assert "[REDACTED]" in out


def test_redacts_bearer_token() -> None:
    out = redact("curl -H 'Authorization: Bearer eyJabcdefghijklmno.def.ghi' ...")
    assert "eyJabcdefghijklmno.def.ghi" not in out
    assert "[REDACTED]" in out


def test_redacts_password_assignment() -> None:
    out = redact('config.password = "p@ssw0rd!"')
    assert "p@ssw0rd!" not in out


def test_redacts_user_supplied_pattern() -> None:
    out = redact("internal_id=ZZ-9999", extra_patterns=[r"internal_id=\S+"])
    assert "ZZ-9999" not in out


def test_no_match_passes_through() -> None:
    src = "Just normal conversation about code."
    assert redact(src) == src


def test_builtin_patterns_present() -> None:
    names = {name for name, _ in BUILTIN_PATTERNS}
    for required in {"env_var_secret", "bearer_token", "password_assignment", "jwt"}:
        assert required in names
