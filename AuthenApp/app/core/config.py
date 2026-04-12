import logging
import os
from pydantic import EmailStr, AnyUrl, BeforeValidator, model_validator, computed_field
from typing import Literal, Annotated, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self
import warnings


KEY_DIR = os.getenv("PRIVATE_KEY_PATH")
class KeyStore:
    private_key = None
    public_key = None
    @classmethod
    def load_key(cls):

        private_key_pem_path = os.path.join(KEY_DIR, "private.pem")
        public_key_pem_path = os.path.join(KEY_DIR, "public.pem")
        logging.warning("Loading private key from: {}".format(private_key_pem_path))
        logging.warning("Loading public key from: {}".format(public_key_pem_path))
        if cls.private_key is None or cls.public_key is None:
            with open(private_key_pem_path, "rb") as key_file:
                cls.private_key = key_file.read()
            with open(public_key_pem_path, "rb") as key_file:
                cls.public_key = key_file.read()
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
    PROJECT_NAME: str | None = None
    FRONTEND_HOST: str
    MONGO_URI:str
    PREFIX_API:str = "/api/v1"
    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
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
    FRONEND_HOST: str | None = None
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
