from __future__ import annotations

from typing import Any
import tiktoken
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import HTMLHeaderTextSplitter, RecursiveCharacterTextSplitter

# Pre-load tiktoken encoder for efficient token count calculation
_TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")


def normalize_section(metadata: dict[str, Any]) -> str:
    """Normalize heading metadata (h1, h2, h3) into a single section name.

    If no heading is present (e.g., introductory text before any heading),
    it defaults to 'article_intro'.

    Args:
        metadata: Metadata dictionary produced by HTMLHeaderTextSplitter.

    Returns:
        Normalized section name string.
    """
    if not metadata:
        return "article_intro"

    # Prioritize subheadings (h2, then h1, then h3)
    for key in ("h2", "h1", "h3"):
        val = metadata.get(key)
        if val and str(val).strip():
            return str(val).strip()

    return "article_intro"


def extract_base_metadata(article: dict[str, Any]) -> dict[str, Any]:
    """Extract standard metadata fields matching the news_articles schema.

    Schema mapping:
        - article_id: mapped from 'id', 'article_id', or 'articles_id'
        - title: article title
        - source: news source (e.g., 'finnhub')
        - published_at: ISO formatted string or None
        - symbol: stock ticker symbol (e.g., 'AAPL')
        - url: original article URL
    """
    article_id = (
        article.get("article_id")
        or article.get("id")
        or article.get("articles_id")
        or ""
    )

    published_at = article.get("published_at")
    if hasattr(published_at, "isoformat"):
        pub_at_str = published_at.isoformat()
    elif published_at is not None:
        pub_at_str = str(published_at)
    else:
        pub_at_str = None

    return {
        "article_id": str(article_id),
        "title": str(article.get("title") or ""),
        "source": str(article.get("source") or ""),
        "published_at": pub_at_str,
        "symbol": str(article.get("symbol") or ""),
        "url": str(article.get("url") or ""),
    }


def chunk_article(
    article: dict[str, Any],
    chunk_size: int = 450,
    chunk_overlap: int = 0,
) -> list[Document]:
    """Split an article into chunks with normalized section metadata.

    Headings (h1, h2, h3) are normalized into the 'section' field.
    Any text appearing before headings or without headings will have
    section set to 'article_intro'.

    Args:
        article: Dictionary representing a news article record.
        chunk_size: Token limit per chunk using cl100k_base encoding.
        chunk_overlap: Overlap token size between chunks.

    Returns:
        List of LangChain Document objects with enriched chunk metadata.
    """
    content = article.get("content") or ""
    if not str(content).strip():
        return []

    # Clean technical non-content tags from HTML
    soup = BeautifulSoup(str(content), "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "link", "svg", "iframe"]):
        tag.decompose()
    clean_html = str(soup)

    # Split HTML by headers
    header_splitter = HTMLHeaderTextSplitter(
        headers_to_split_on=[
            ("h1", "h1"),
            ("h2", "h2"),
            ("h3", "h3"),
        ],
        return_each_element=False,
    )
    sections = header_splitter.split_text(clean_html)

    base_metadata = extract_base_metadata(article)
    clean_sections: list[Document] = []

    for doc in sections:
        # Detect heading-only docs
        header_values = {
            str(v).strip().casefold()
            for k, v in doc.metadata.items()
            if k.startswith("h")
        }

        text = doc.page_content.strip()
        if not text or text.casefold() in header_values:
            continue

        section_name = normalize_section(doc.metadata)

        chunk_metadata = {
            **base_metadata,
            "section": section_name,
        }

        clean_sections.append(
            Document(page_content=text, metadata=chunk_metadata)
        )

    if not clean_sections:
        return []

    # Chunk with tiktoken cl100k_base encoder
    chunk_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = chunk_splitter.split_documents(clean_sections)

    # Enrich chunks with index and exact token count
    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = idx
        chunk.metadata["token_count"] = len(_TIKTOKEN_ENCODER.encode(chunk.page_content))

    return chunks


def get_chunks_from_url(
    html: str,
    article: dict[str, Any] | None = None,
    chunk_size: int = 450,
    chunk_overlap: int = 0,
) -> list[Document]:
    """Helper function to chunk raw HTML content, optionally with article metadata."""
    article_dict = article.copy() if article else {}
    article_dict["content"] = html
    return chunk_article(article_dict, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
