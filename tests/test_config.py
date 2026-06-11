from world_cup_intel.config import Settings


def test_settings_from_env_reads_database_and_email_values(monkeypatch, tmp_path):
    db_path = tmp_path / "world-cup.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WCI_EMAIL_SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("WCI_EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("WCI_EMAIL_USERNAME", "sender@qq.com")
    monkeypatch.setenv("WCI_EMAIL_PASSWORD", "smtp-auth-code")
    monkeypatch.setenv("WCI_EMAIL_RECIPIENT", "receiver@example.com")

    settings = Settings.from_env()

    assert settings.database_url.endswith("world-cup.db")
    assert settings.email.smtp_host == "smtp.qq.com"
    assert settings.email.smtp_port == 465
    assert settings.email.username == "sender@qq.com"
    assert settings.email.recipient == "receiver@example.com"
