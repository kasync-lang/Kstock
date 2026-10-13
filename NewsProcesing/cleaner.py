import re
import unicodedata
from bs4 import BeautifulSoup


def clean_html(html_content: str | None, separator: str = " ") -> str:
    """Strip all HTML tags and elements, retaining only plain text.

    Args:
        html_content: Raw HTML string to be cleaned.
        separator: String used to join text elements across tags. Defaults to a single space.

    Returns:
        Cleaned plain text string.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove non-content and technical tags
    for tag in soup(["script", "style", "noscript", "meta", "link", "svg", "iframe", "template"]):
        tag.decompose()

    # Extract plain text
    text = soup.get_text(separator=separator, strip=True)

    # Normalize consecutive whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip() if separator == "\n" else re.sub(r"\s+", " ", text).strip()

    return text


def prepare_text_for_dedup(extracted_html: str | None) -> str:
    """Normalize text extracted from HTML for fingerprinting or deduplication (e.g., SimHash).

    Args:
        extracted_html: Raw HTML string of the article.

    Returns:
        Normalized lowercase text with unified Unicode representation.
    """
    text = clean_html(extracted_html, separator=" ")
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.casefold()

    return text
