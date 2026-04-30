from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


def clean_text(text: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonicalize_url(url: str | None, *, base_url: str | None = None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    absolute = urljoin(base_url or "", raw)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return absolute
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_QUERY_KEYS]
    cleaned = parsed._replace(netloc=parsed.netloc.lower(), query=urlencode(query), fragment="")
    path = cleaned.path.rstrip("/") if cleaned.path != "/" else cleaned.path
    return urlunparse(cleaned._replace(path=path))


def normalized_title_key(title: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", title or "").casefold()


def compute_content_hash(value: dict[str, object]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Article:
    provider: str
    site: str
    url: str
    canonical_url: str
    dedupe_key: str
    title: str
    published_at: str | None
    category: str
    scope: str
    summary: str
    body_text: str | None
    language: str
    fetch_status: str
    parse_status: str
    source_quality: float
    content_hash: str = ""

    def with_hash(self) -> Article:
        payload = self._hash_payload()
        return replace(self, content_hash=compute_content_hash(payload))

    def _hash_payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "site": self.site,
            "canonical_url": self.canonical_url,
            "dedupe_key": self.dedupe_key,
            "title": self.title,
            "published_at": self.published_at or "",
            "category": self.category,
            "scope": self.scope,
            "summary": self.summary,
            "body_text": self.body_text or "",
            "language": self.language,
            "fetch_status": self.fetch_status,
            "parse_status": self.parse_status,
            "source_quality": self.source_quality,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.site,
            "provider": self.provider,
            "site": self.site,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "dedupe_key": self.dedupe_key,
            "title": self.title,
            "published_at": self.published_at or "",
            "category": self.category,
            "scope": self.scope,
            "summary": self.summary,
            "body_text": self.body_text,
            "language": self.language,
            "fetch_status": self.fetch_status,
            "parse_status": self.parse_status,
            "confidence": self.source_quality,
            "source_quality": self.source_quality,
            "content_hash": self.content_hash or self.with_hash().content_hash,
        }


def make_article(
    *,
    provider: str,
    site: str,
    url: str,
    title: str,
    category: str,
    scope: str,
    summary: str = "",
    published_at: str | None = None,
    body_text: str | None = None,
    language: str = "ko",
    fetch_status: str = "ok",
    parse_status: str = "metadata",
    source_quality: float = 0.55,
    canonical_url: str | None = None,
    dedupe_key: str | None = None,
) -> Article:
    canonical = canonicalize_url(canonical_url or url)
    title_key = normalized_title_key(title)
    dedupe = dedupe_key or (canonical if canonical else f"title:{category}:{scope}:{title_key}")
    return Article(
        provider=provider,
        site=site,
        url=url,
        canonical_url=canonical,
        dedupe_key=dedupe,
        title=title,
        published_at=published_at,
        category=category,
        scope=scope,
        summary=summary,
        body_text=body_text,
        language=language,
        fetch_status=fetch_status,
        parse_status=parse_status,
        source_quality=source_quality,
    ).with_hash()


def dedupe_articles(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    result: list[Article] = []
    for article in articles:
        title_key = normalized_title_key(article.title)
        title_dedupe = f"title:{article.category}:{title_key}" if title_key else ""
        candidates = [key for key in (article.dedupe_key, article.canonical_url, title_dedupe) if key]
        if not candidates or any(candidate in seen for candidate in candidates):
            continue
        seen.update(candidates)
        result.append(article)
    return result
