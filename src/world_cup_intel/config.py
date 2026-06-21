from dataclasses import dataclass
import os


@dataclass(frozen=True)
class EmailSettings:
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    recipient: str


@dataclass(frozen=True)
class Settings:
    database_url: str
    email: EmailSettings

    @classmethod
    def database_url_from_env(cls) -> str:
        return os.environ["WCI_DATABASE_URL"]

    @staticmethod
    def email_from_env() -> EmailSettings:
        return EmailSettings(
            smtp_host=os.environ["WCI_EMAIL_SMTP_HOST"],
            smtp_port=int(os.environ["WCI_EMAIL_SMTP_PORT"]),
            username=os.environ["WCI_EMAIL_USERNAME"],
            password=os.environ["WCI_EMAIL_PASSWORD"],
            recipient=os.environ["WCI_EMAIL_RECIPIENT"],
        )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=cls.database_url_from_env(),
            email=cls.email_from_env(),
        )
