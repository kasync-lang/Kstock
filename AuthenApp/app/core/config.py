import json
import logging
import os
from pathlib import Path

from pydantic import EmailStr, AnyUrl, BeforeValidator, model_validator, computed_field, BaseModel
from typing import Literal, Annotated, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self
import warnings


KEY_DIR = os.getenv("PRIVATE_KEY_PATH", ".")


class GoogleOAuthConfig(BaseModel):
    client_id: str
    client_secret: str
    auth_uri: str
    token_uri: str
    redirect_uris: list[str]
class KeyStore:
    private_key = None
    public_key = None
    @classmethod
    def load_key(cls):
        private_key_pem_path = os.path.join(KEY_DIR, "private.pem")
        public_key_pem_path = os.path.join(KEY_DIR, "public.pem")
        secrets_client_google_path = os.path.join(KEY_DIR, "client_secret.json")
        logging.warning("Loading Google client secrets from: {}".format(secrets_client_google_path))
        logging.warning("Loading private key from: {}".format(private_key_pem_path))
        logging.warning("Loading public key from: {}".format(public_key_pem_path))
        if cls.private_key is None or cls.public_key is None:
            with open(private_key_pem_path, "rb") as key_file:
                cls.private_key = key_file.read()
            with open(public_key_pem_path, "rb") as key_file:
                cls.public_key = key_file.read()
        if not os.path.exists(secrets_client_google_path):
            logging.warning(f"Google client secrets file not found at {secrets_client_google_path}")
def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)
class Setting(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(KEY_DIR,".env"),
        env_ignore_empty=True,
        extra="ignore"
    )
    ENVIRONMENT :Literal["dev", "test", "prod"] = "dev"
    GOOGLE_CLIENT_SECRET_PATH: str = os.path.join(KEY_DIR, "client_secret.json")
    # Loaded from GOOGLE_CLIENT_SECRET_PATH after settings have read environment
    # overrides; it is not an input environment setting itself.
    google_oauth: GoogleOAuthConfig | None = None

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: EmailStr | None = None
    PROJECT_NAME: str | None = "Kstock Authentication"
    REDIS_HOST: str
    REDIS_PORT: int
    FRONTEND_HOST: str
    FRONTEND_URL: str = "http://localhost:5173"
    MONGO_URI:str
    PREFIX_API:str = ""

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    @model_validator(mode="after")
    def load_google_secret(self) -> Self:
        secret_file = Path(self.GOOGLE_CLIENT_SECRET_PATH)
        with secret_file.open(encoding="utf-8") as f:
            raw = json.load(f)

        oauth_data = raw.get("web") or raw.get("installed")

        if not isinstance(oauth_data, dict):
            raise ValueError(
                f"Invalid Google OAuth credentials in {secret_file}: "
                'expected a top-level "web" or "installed" object.'
            )

        self.google_oauth = GoogleOAuthConfig(
            client_id=oauth_data["client_id"],
            client_secret=oauth_data["client_secret"],
            auth_uri=oauth_data["auth_uri"],
            token_uri=oauth_data["token_uri"],
            redirect_uris=oauth_data.get("redirect_uris", []),
        )

        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_EMAIL: EmailStr
    FIRST_SUPERUSER_PASSWORD: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    REFRESH_TOKEN_COOKIE_SECURE: bool = False
    REFRESH_TOKEN_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    REFRESH_TOKEN_COOKIE_PATH: str = "/"
    FRONTEND_HOST: str | None = None
    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "dev":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self

settings = Setting()
if __name__ == "__main__":
    print(settings.FIRST_SUPERUSER)
