from __future__ import annotations

import hashlib
import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from ingestion.model.news_model import NewsRaw
from ingestion.source.api_config import NewsApiConfig

logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def load_symbols(file_path: Path | None = None) -> list[str]:
    """Load symbols from list_symbol.txt (one symbol per line)."""

    fp = file_path or (BASE_DIR / "list_symbol.txt")
    if not fp.exists():
        raise FileNotFoundError(f"Symbols file not found: {fp}")
    symbols = [s.strip() for s in fp.read_text(encoding="utf-8").splitlines() if s.strip()]
    if not symbols:
        raise ValueError(f"Symbols file is empty: {fp}")
    return symbols




class APIGeter:

    def __init__(
        self,
        config: NewsApiConfig | None = None,
        *,
        session: requests.Session | None = None,
        max_retries: int = 5,
        retry_backoff_s: float = 10,
    ) -> None:
        self._config = config or NewsApiConfig.from_env()
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": self._config.user_agent, "Accept": "application/json"})
        self._max_retries = max_retries
        self._retry_backoff_s = retry_backoff_s


    def fetch_company_news(self, symbol: str, *, from_date: date, to_date: date) -> list[dict[str, Any]]:
        """Fetch raw news items for a symbol within a date range (inclusive)."""

        provider = self._config.provider
        if provider != "finnhub":
            raise NotImplementedError(f"Unsupported provider: {provider!r}. Set NEWS_API_PROVIDER=finnhub")

        url = f"{self._config.base_url}/company-news"
        params = {
            "symbol": symbol,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "token": self._config.token,
        }
        return self._get_json_list(url, params=params)

    def _get_json_list(self, url: str, *, params: dict[str, Any]) -> list[dict[str, Any]]:
        last_err: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.get(url, params=params, timeout=self._config.timeout_s)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    sleep_s = float(retry_after) if retry_after and retry_after.isdigit() else self._retry_backoff_s * attempt
                    logger.warning("Rate limited (429). Sleeping %.2fs then retrying...", sleep_s)
                    self._config.km.rotate_key()
                    self._config.token = self._config.km.get_key()
                    params.update({"token": self._config.token})
                    time.sleep(sleep_s)
                    continue
                resp.raise_for_status()
                data = resp.json()
                if data is None:
                    return []
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict)]
                # Finnhub sometimes returns {"error": "..."}
                if isinstance(data, dict) and data.get("error"):
                    raise RuntimeError(f"API error: {data.get('error')}")
                raise TypeError(f"Unexpected JSON type: {type(data).__name__}")
            except (requests.Timeout, requests.ConnectionError) as e:
                last_err = e
                sleep_s = self._retry_backoff_s * attempt
                logger.warning("HTTP transient error: %s. Retrying in %.2fs (%d/%d)", e, sleep_s, attempt, self._max_retries)
                time.sleep(sleep_s)
            except requests.HTTPError as e:
                last_err = e
                # Retry on 5xx; fail fast on 4xx (except 429 handled above)
                status = getattr(e.response, "status_code", None)
                if status and 500 <= status <= 599 and attempt < self._max_retries:
                    sleep_s = self._retry_backoff_s * attempt *2
                    logger.warning("HTTP %s from API. Retrying in %.2fs (%d/%d)", status, sleep_s, attempt, self._max_retries)
                    time.sleep(sleep_s)
                    continue
                raise
            except Exception as e:  # JSON decode errors etc.
                last_err = e
                if attempt < self._max_retries:
                    sleep_s = self._retry_backoff_s * attempt
                    logger.warning("API parse error: %s. Retrying in %.2fs (%d/%d)", e, sleep_s, attempt, self._max_retries)
                    time.sleep(sleep_s)
                    continue
                raise

        # Should not reach here, but keep mypy happy.
        raise RuntimeError("Failed to fetch news") from last_err

    @staticmethod
    def _stable_id(*, source: str, url: str, published_at: datetime | None) -> str:
        base = f"{source}|{url}|{published_at.isoformat() if published_at else ''}".encode("utf-8")
        return hashlib.sha256(base).hexdigest()[:32]

    def parse_news_item(self, item: dict[str, Any], *, symbol: str) -> NewsRaw:
        """Convert provider payload -> NewsRaw."""

        provider = self._config.provider
        if provider != "finnhub":
            raise NotImplementedError(f"Unsupported provider: {provider!r}")

        # Finnhub schema: https://finnhub.io/docs/api/company-news
        title = str(item.get("headline") or "").strip()
        content = str(item.get("summary") or "").strip()
        url = str(item.get("url") or "").strip()
        image_url = item.get("image") or None
        category = item.get("category") or None

        dt = None
        try:
            # "datetime" is epoch seconds
            epoch = item.get("datetime")
            if isinstance(epoch, (int, float)):
                dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        except Exception:
            dt = None

        if not url:
            # If URL is missing, create one based on title to avoid breaking downstream.
            url = f"{provider}://{symbol}/{self._stable_id(source=provider, url=title, published_at=dt)}"

        news_id = str(item.get("id") or "").strip()
        if not news_id:
            news_id = self._stable_id(source=provider, url=url, published_at=dt)

        return NewsRaw(
            id=news_id,
            source=provider,
            title=title,
            content=content,
            url=url,
            image_url=str(image_url) if image_url else None,
            category=str(category) if category else None,
            symbol=symbol,
            published_at=dt or datetime.now(tz=timezone.utc),
            raw_payload=item,
        )

    def fetch_news_raw(self, symbol: str, *, from_date: date, to_date: date) -> list[NewsRaw]:
        raw_items = self.fetch_company_news(symbol, from_date=from_date, to_date=to_date)
        out: list[NewsRaw] = []
        for it in raw_items:
            try:
                out.append(self.parse_news_item(it, symbol=symbol))
            except Exception:
                logger.exception("Failed to parse news item for %s: %r", symbol, it)
        return out

    def fetch_many(self, symbols: Iterable[str], *, from_date: date, to_date: date) -> list[NewsRaw]:
        all_items: list[NewsRaw] = []
        for s in symbols:
            s = str(s).strip()
            if not s:
                continue
            items = self.fetch_news_raw(s, from_date=from_date, to_date=to_date)
            all_items.extend(items)
        return all_items


# Backwards-compatible module-level symbols load (optional)
try:
    symbols = load_symbols()
except Exception:
    symbols = []
