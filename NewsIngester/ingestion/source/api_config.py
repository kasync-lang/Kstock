from dotenv import load_dotenv
from dataclasses import dataclass
import os



class APIKeyManager:
    def __init__(self, keys):
        self.keys = keys
        self.index = 0
    def get_key(self):
        return self.keys[self.index]
    def rotate_key(self):
        self.index = (self.index + 1) % len(self.keys)
@dataclass(frozen=False, slots=True)
class NewsApiConfig:
    km: APIKeyManager
    provider: str
    base_url: str
    token: str
    timeout_s: float = 20.0
    user_agent: str = "Chrome/146.0.0.0 Safari/537.36"
    @staticmethod
    def from_env() -> "NewsApiConfig":
        """Configuration via env (supports existing SECRET_KEY_HUB name)."""
        load_dotenv(override=False)
        provider = os.getenv("NEWS_API_PROVIDER", "finnhub").lower().strip()
        base_url = os.getenv("NEWS_API_BASE_URL", "https://finnhub.io/api/v1").rstrip("/")
        km = APIKeyManager(os.getenv("SECRET_KEY_HUB").split(","))
        token =  km.get_key()
        if not token:
            raise ValueError(
                "Missing API token env var: FINNHUB_TOKEN (or SECRET_KEY_HUB / NEWS_API_TOKEN)"
            )
        timeout_s = float(os.getenv("NEWS_HTTP_TIMEOUT_S", "20"))
        user_agent = os.getenv("NEWS_USER_AGENT", "NewsProcess/1.0")
        return NewsApiConfig(provider=provider, base_url=base_url, token=token, timeout_s=timeout_s, user_agent=user_agent, km=km)
