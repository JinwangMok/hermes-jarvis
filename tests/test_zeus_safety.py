import pytest

from zeus_os.zeus_os import safety


class TestRedaction:
    def test_redacts_discord_token(self):
        token = ".".join(["M" + "A" * 23, "B" * 6, "C" * 27])
        text = f"My bot token is {token}"
        result = safety._replace_secrets(text)
        assert "[REDACTED]" in result

    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer " + "a" * 30
        result = safety._replace_secrets(text)
        assert "[REDACTED]" in result

    def test_redacts_api_key(self):
        key_name = "api" + "_key"
        secret_value = "sk-" + "a" * 20
        text = f'{key_name} = "{secret_value}"'
        result = safety._replace_secrets(text)
        assert "[REDACTED]" in result

    def test_redacts_private_key(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        result = safety._replace_secrets(text)
        assert "[REDACTED]" in result

    def test_redacts_reasoning_fields(self):
        obj = {"chain_of_thought": "I think therefore I am", "answer": "42"}
        result = safety.redact_value(obj)
        assert result["chain_of_thought"] == "[REDACTED: reasoning]"
        assert result["answer"] == "42"

    def test_redact_json_parses_and_redacts(self):
        key_name = "api" + "_key"
        secret_value = "sk-" + "b" * 20
        json_text = f'{{"{key_name}": "{secret_value}", "name": "test"}}'
        result = safety.redact_json(json_text)
        assert secret_value not in result
        assert "test" in result

    def test_scan_for_secrets_finds_matches(self):
        text = "Bearer abc123def456ghi789jkl012mno345pqr678 and another"
        findings = safety.scan_for_secrets(text)
        assert len(findings) >= 1

    def test_scan_for_secrets_does_not_return_secret_text(self):
        text = "Bearer " + "a" * 30
        findings = safety.scan_for_secrets(text)
        assert findings
        assert "matched" not in findings[0]
        assert findings[0]["length"] > 0


class TestPathSafety:
    def test_rejects_absolute_path(self):
        assert safety.is_safe_relative_path("/etc/passwd") is False

    def test_rejects_parent_traversal(self):
        assert safety.is_safe_relative_path("../../etc/passwd") is False

    def test_rejects_dot_dot_in_parts(self):
        assert safety.is_safe_relative_path("foo/../bar") is False

    def test_accepts_safe_relative_path(self):
        assert safety.is_safe_relative_path("foo/bar/baz.txt") is True

    def test_resolve_safe_path_under_base(self):
        from pathlib import Path
        base = Path("/tmp/zeus_test_base")
        base.mkdir(parents=True, exist_ok=True)
        resolved = safety.resolve_safe_path(base, "task_1/artifact.txt")
        assert resolved.is_relative_to(base)

    def test_resolve_safe_path_rejects_escape(self):
        from pathlib import Path
        base = Path("/tmp/zeus_test_base")
        base.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError):
            safety.resolve_safe_path(base, "../escape.txt")

    def test_sha256_hex_deterministic(self):
        h1 = safety.sha256_hex(b"hello")
        h2 = safety.sha256_hex(b"hello")
        assert h1 == h2
        assert len(h1) == 64

    def test_compute_file_hash(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = safety.compute_file_hash(f)
        assert len(h) == 64
        assert h == safety.sha256_hex(b"hello world")
