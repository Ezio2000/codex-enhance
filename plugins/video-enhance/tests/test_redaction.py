from video_enhance_mcp.errors import redact


def test_redact_removes_exact_and_bearer_secrets() -> None:
    secret = "private-token-value"
    value = redact(
        f"Authorization: Bearer {secret}; key={secret}; extra=sk-visible123", secret
    )
    assert secret not in value
    assert "sk-visible123" not in value
    assert value.count("[REDACTED]") >= 2
