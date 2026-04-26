from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, quote_plus, unquote, urljoin, urlencode, urlparse, urlunparse

import requests
import shutil
import subprocess
import yaml

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig
from .news_center import collect_news_center

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
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
HN_PREFIX_RE = re.compile(r"^(show|ask|tell)\s+hn\s*:\s*", re.I)
HTML_PATH_HINT_RE = re.compile(r"/(news|blog|post|posts|article|articles|press|announcements?|research|stories?)/", re.I)
HTML_BLOCKLIST_RE = re.compile(r"/(tag|category|author|page|privacy|terms|login|signup|contact|about|careers)/", re.I)
X_STATUS_ID_RE = re.compile(r"(?:^|/)status(?:es)?/(\d+)(?:$|[/?#])", re.I)
NITTER_STATUS_URL_RE = re.compile(r"https?://(?:www\.)?nitter\.net/([^/?#]+)/status/(\d+)", re.I)
X_STATUS_URL_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/([^/?#]+)/status/(\d+)", re.I)
X_METRIC_PATTERNS = {
    "reply_count": re.compile(r'"reply_count"\s*:\s*"?([0-9][0-9,]*(?:\.[0-9]+)?[KMB]?)"?', re.I),
    "retweet_count": re.compile(r'"retweet_count"\s*:\s*"?([0-9][0-9,]*(?:\.[0-9]+)?[KMB]?)"?', re.I),
    "quote_count": re.compile(r'"quote_count"\s*:\s*"?([0-9][0-9,]*(?:\.[0-9]+)?[KMB]?)"?', re.I),
    "favorite_count": re.compile(r'"favorite_count"\s*:\s*"?([0-9][0-9,]*(?:\.[0-9]+)?[KMB]?)"?', re.I),
}


@dataclass(frozen=True)
class WatchSource:
    source_id: str
    display_name: str
    company_tag: str | None
    source_class: str | None
    source_role: str
    source_type: str
    ingest_strategy: str
    base_url: str
    feed_url: str | None
    html_list_url: str | None
    poll_minutes: int
    enabled: bool
    validation_status: str | None
    validation_notes: tuple[str, ...]
    browser_required: bool
    anti_bot_risk: str | None
    priority_weight: float
    reaction_weight: float
    cooldown_minutes: int
    topic_tags: tuple[str, ...]
    file_path: Path


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str | None]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        self._current_href = attr_map.get("href")
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        text = " ".join(part.strip() for part in self._current_text if part.strip()).strip()
        self.links.append({"href": self._current_href, "text": text or None})
        self._current_href = None
        self._current_text = []


class _ReadableTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if len(text) >= 20:
            self.parts.append(text)


def _compact_excerpt(text: str | None, *, limit: int = 1200) -> str | None:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return None
    return cleaned[: limit - 1].rstrip() + "…" if len(cleaned) > limit else cleaned


def _extract_readable_text(html: str) -> str | None:
    parser = _ReadableTextExtractor()
    try:
        parser.feed(html)
    except Exception:
        return None
    return _compact_excerpt(" ".join(parser.parts), limit=1600)


def _search_url_for_title(title: str | None) -> str | None:
    normalized = _normalize_title(title)
    if not normalized:
        return None
    return f"https://duckduckgo.com/html/?q={quote_plus(normalized)}"


def _decode_search_result_href(href: str | None) -> str | None:
    if not href:
        return None
    candidate = unquote(str(href).strip())
    parsed = urlparse(candidate)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "uddg" in query:
        candidate = unquote(query["uddg"])
        parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = parsed.netloc.lower()
    if any(blocked in host for blocked in ("duckduckgo.com", "google.com", "bing.com")):
        return None
    return _canonicalize_url(candidate)


def _search_result_urls(search_html: str) -> list[str]:
    parser = _LinkCollector()
    try:
        parser.feed(search_html)
    except Exception:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for link in parser.links:
        decoded = _decode_search_result_href(link.get("href"))
        if decoded and decoded not in seen:
            seen.add(decoded)
            urls.append(decoded)
    return urls


def _search_for_item_content(item: dict, fetch_text) -> tuple[str | None, str | None]:
    search_url = _search_url_for_title(str(item.get("title") or ""))
    if not search_url:
        return None, None
    try:
        candidates = _search_result_urls(fetch_text(search_url))
    except Exception:
        return None, None
    original_url = _canonicalize_url(str(item.get("url") or ""))
    for candidate_url in candidates[:5]:
        if original_url and candidate_url == original_url:
            continue
        try:
            excerpt = _extract_readable_text(fetch_text(candidate_url))
        except Exception:
            excerpt = None
        if excerpt:
            return excerpt, candidate_url
    return None, None


def _enrich_item_content(item: dict, fetch_text, *, allow_search_fallback: bool = True) -> dict:
    enriched = dict(item)
    feed_summary = _compact_excerpt(str(item.get("summary_text") or ""), limit=900)
    article_excerpt = None
    content_source_url = None
    url = str(item.get("url") or "").strip()
    if url and url.lower() != "n/a":
        try:
            article_excerpt = _extract_readable_text(fetch_text(url))
            if article_excerpt:
                content_source_url = _canonicalize_url(url)
        except Exception:
            article_excerpt = None
    if not article_excerpt and allow_search_fallback:
        article_excerpt, content_source_url = _search_for_item_content(item, fetch_text)
    if article_excerpt:
        enriched["content_excerpt"] = article_excerpt
        if content_source_url:
            enriched["content_source_url"] = content_source_url
    if feed_summary and not enriched.get("summary_text"):
        enriched["summary_text"] = feed_summary
    return enriched


def _enrich_items_with_bounded_search_fallback(items: list[dict], fetch_text, *, search_fallback_limit: int = 3) -> list[dict]:
    enriched_items: list[dict] = []
    remaining_searches = max(0, search_fallback_limit)
    for item in items:
        enriched = _enrich_item_content(item, fetch_text, allow_search_fallback=remaining_searches > 0)
        if enriched.get("content_excerpt"):
            original_excerpt = dict(item).get("content_excerpt")
            if not original_excerpt and enriched.get("content_source_url") != _canonicalize_url(str(item.get("url") or "")):
                remaining_searches -= 1
        elif remaining_searches > 0:
            remaining_searches -= 1
        enriched_items.append(enriched)
    return enriched_items


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _safe_text(node, path: str) -> str | None:
    found = node.find(path)
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _parse_dt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat()
        parsed = datetime.fromisoformat(value)
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC).isoformat()
    except Exception:
        pass
    try:
        return parsedate_to_datetime(value).astimezone(UTC).isoformat()
    except Exception:
        return None


def _canonicalize_url(url: str | None, *, base_url: str | None = None) -> str:
    raw = (url or "").strip()
    if not raw:
        return (base_url or "").strip()
    absolute = urljoin(base_url or "", raw)
    parsed = urlparse(absolute)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_QUERY_KEYS]
    cleaned = parsed._replace(query=urlencode(query), fragment="")
    return urlunparse(cleaned)


def _canonical_issue_key(url: str | None, title: str | None = None) -> str:
    canonical = _canonicalize_url(url)
    if canonical and canonical.lower() != "n/a":
        parsed = urlparse(canonical)
        path = parsed.path.rstrip("/") or parsed.path
        cleaned = parsed._replace(netloc=parsed.netloc.lower(), path=path)
        return urlunparse(cleaned)
    return f"title:{_normalize_title(title)}"


def _normalize_title(title: str | None) -> str:
    text = (title or "").strip()
    text = HN_PREFIX_RE.sub("", text)
    text = re.sub(r"^[\[【(].*?[\]】)]\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.casefold().strip()


def _story_key(title: str | None, company_tag: str | None) -> str:
    base = _normalize_title(title)
    return f"{company_tag or 'global'}::{base}"


def _parse_json_feed(text: str, source: WatchSource) -> list[dict]:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return []
    candidates = raw.get("items") or raw.get("entries") or raw.get("articles") or raw.get("data") or []
    if isinstance(candidates, dict):
        candidates = candidates.get("items") or candidates.get("entries") or []
    items: list[dict] = []
    for item in candidates[:20] if isinstance(candidates, list) else []:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("headline") or item.get("name") or source.display_name
        link = item.get("url") or item.get("link") or item.get("href") or source.base_url
        summary = item.get("description") or item.get("summary") or item.get("excerpt") or item.get("text")
        published = _parse_dt(item.get("pubDate") or item.get("published_at") or item.get("published") or item.get("date")) or _utc_now().isoformat()
        items.append({
            "title": str(title),
            "url": _canonicalize_url(str(link), base_url=source.base_url),
            "summary_text": str(summary) if summary else None,
            "published_at": published,
            "external_id": str(item.get("id") or item.get("guid") or link),
        })
    return items


def _parse_rss_or_atom(text: str, source: WatchSource) -> list[dict]:
    if text.lstrip().startswith(("{", "[")):
        return _parse_json_feed(text, source)
    root = ET.fromstring(text)
    items: list[dict] = []
    if root.tag.endswith("rss"):
        channel = root.find("channel")
        if channel is None:
            return items
        for item in channel.findall("item")[:20]:
            title = _safe_text(item, "title") or source.display_name
            link = _canonicalize_url(_safe_text(item, "link"), base_url=source.base_url)
            summary = _safe_text(item, "description")
            published = _parse_dt(_safe_text(item, "pubDate")) or _utc_now().isoformat()
            guid = _safe_text(item, "guid")
            items.append({
                "title": title,
                "url": link,
                "summary_text": summary,
                "published_at": published,
                "external_id": guid,
            })
        return items

    if root.tag.endswith("feed"):
        for entry in root.findall("atom:entry", ATOM_NS)[:20]:
            title_node = entry.find("atom:title", ATOM_NS)
            title = title_node.text.strip() if title_node is not None and title_node.text else source.display_name
            link_node = entry.find("atom:link", ATOM_NS)
            link = _canonicalize_url(link_node.get("href") if link_node is not None else None, base_url=source.base_url)
            summary_node = entry.find("atom:summary", ATOM_NS) or entry.find("atom:content", ATOM_NS)
            summary = summary_node.text.strip() if summary_node is not None and summary_node.text else None
            updated_node = entry.find("atom:updated", ATOM_NS) or entry.find("atom:published", ATOM_NS)
            published = _parse_dt(updated_node.text.strip() if updated_node is not None and updated_node.text else None) or _utc_now().isoformat()
            external_node = entry.find("atom:id", ATOM_NS)
            external_id = external_node.text.strip() if external_node is not None and external_node.text else None
            items.append({
                "title": title,
                "url": link,
                "summary_text": summary,
                "published_at": published,
                "external_id": external_id,
            })
    return items


def _parse_count_value(value: str | int | float | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    multiplier = 1
    suffix = text[-1].upper()
    if suffix in {"K", "M", "B"}:
        text = text[:-1]
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def extract_x_status_id(*values: str | None) -> str | None:
    for value in values:
        if not value:
            continue
        text = str(value).strip()
        if not text:
            continue
        match = X_STATUS_ID_RE.search(text)
        if match:
            return match.group(1)
        if text.isdigit():
            return text
    return None


def _extract_x_handle(source: WatchSource, *values: str | None) -> str | None:
    for value in [*values, source.feed_url, source.base_url, source.html_list_url]:
        if not value:
            continue
        text = str(value).strip()
        nitter_match = NITTER_STATUS_URL_RE.search(text)
        if nitter_match:
            return nitter_match.group(1)
        x_match = X_STATUS_URL_RE.search(text)
        if x_match:
            return x_match.group(1)
        parsed = urlparse(text)
        if parsed.netloc.endswith("nitter.net") and parsed.path.endswith("/rss"):
            handle = parsed.path.strip("/").removesuffix("/rss").strip("/")
            if handle:
                return handle
        if parsed.netloc.endswith(("x.com", "twitter.com")):
            parts = [part for part in parsed.path.split("/") if part]
            if parts:
                return parts[0]
    return None


def _looks_like_x_source(source: WatchSource) -> bool:
    return str(source.source_type).lower() == "x" or any(
        value and "nitter.net" in str(value) for value in (source.feed_url, source.base_url, source.html_list_url)
    )


def _build_x_status_url(handle: str, status_id: str) -> str:
    return f"https://x.com/{handle}/status/{status_id}"


def parse_x_status_metrics(text: str) -> dict[str, int]:
    metrics: dict[str, int] = {}
    for key, pattern in X_METRIC_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            continue
        parsed = _parse_count_value(match.group(1))
        if parsed is not None:
            metrics[key] = parsed
    return metrics


def _enrich_x_item(source: WatchSource, item: dict, fetch_text) -> dict:
    enriched = dict(item)
    status_id = extract_x_status_id(item.get("external_id"), item.get("url"), item.get("guid"))
    handle = _extract_x_handle(source, item.get("url"), item.get("external_id"), item.get("guid"))
    if not status_id or not handle:
        return enriched
    enriched["external_id"] = status_id
    enriched["author"] = enriched.get("author") or handle
    enriched["url"] = _build_x_status_url(handle, status_id)
    try:
        metrics = parse_x_status_metrics(fetch_text(enriched["url"]))
    except Exception:
        metrics = {}
    if metrics:
        engagement = dict(enriched.get("engagement") or {})
        engagement.update(metrics)
        engagement.setdefault(
            "score",
            metrics.get("favorite_count", 0) + metrics.get("retweet_count", 0) + metrics.get("quote_count", 0),
        )
        engagement.setdefault("comments", metrics.get("reply_count", 0))
        enriched["engagement"] = engagement
    if not enriched.get("content_excerpt"):
        article_excerpt, content_source_url = _search_for_item_content(enriched, fetch_text)
        if article_excerpt:
            enriched["content_excerpt"] = article_excerpt
            if content_source_url:
                enriched["content_source_url"] = content_source_url
    return enriched


def _fetch_text(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 HermesBot/1.0"}, timeout=12)
    response.raise_for_status()
    return response.text


def _fetch_json(url: str):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 HermesBot/1.0"}, timeout=12)
    response.raise_for_status()
    return response.json()


def _fetch_hackernews(source: WatchSource, fetch_json=_fetch_json, fetch_text=_fetch_text) -> list[dict]:
    top_ids = fetch_json(source.feed_url or source.base_url)[:10]
    items: list[dict] = []
    for item_id in top_ids:
        item = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
        if not item or not item.get("title"):
            continue
        published_at = datetime.fromtimestamp(item.get("time", int(_utc_now().timestamp())), tz=UTC).isoformat()
        item_data = {
            "title": item["title"],
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={item_id}",
            "summary_text": item.get("text"),
            "published_at": published_at,
            "external_id": str(item_id),
            "author": item.get("by"),
            "engagement": {
                "score": item.get("score", 0),
                "comments": item.get("descendants", 0),
            },
        }
        items.append(_enrich_item_content(item_data, fetch_text, allow_search_fallback=len(items) < 3))
    return items


def _parse_html_listing(text: str, source: WatchSource) -> list[dict]:
    parser = _LinkCollector()
    parser.feed(text)
    items: list[dict] = []
    seen_urls: set[str] = set()
    source_host = urlparse(source.base_url).netloc
    for link in parser.links:
        href = _canonicalize_url(link.get("href"), base_url=source.base_url)
        title = (link.get("text") or "").strip()
        if not href or len(title) < 12:
            continue
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != source_host:
            continue
        if HTML_BLOCKLIST_RE.search(parsed.path):
            continue
        if not HTML_PATH_HINT_RE.search(parsed.path):
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)
        items.append(
            {
                "title": title,
                "url": href,
                "summary_text": f"HTML listing candidate from {source.display_name}",
                "published_at": _utc_now().isoformat(),
            }
        )
        if len(items) >= 20:
            break
    return items


def _heuristic_judgment(config: PipelineConfig, *, title: str, primary_company_tag: str | None, signal_count: int, unique_source_count: int, engagement_score: float, reaction_score: float) -> dict:
    importance = 0.12
    if primary_company_tag:
        importance += 0.14
    importance += min(0.22, 0.07 * max(0, signal_count - 1))
    importance += min(0.18, 0.10 * max(0, unique_source_count - 1))
    importance += min(0.20, engagement_score / 8000.0)
    importance += min(0.18, reaction_score / 3000.0)
    importance = min(1.0, importance)
    momentum = min(1.0, max(0.0, (unique_source_count - 1) * 0.10 + (reaction_score / 3000.0)))
    heat = "critical" if importance >= 0.95 else "high" if importance >= 0.82 else "medium" if importance >= 0.65 else "low"
    return {
        "engine": "heuristic-fallback",
        "configured_model": config.watch.adjudicator_model,
        "fallback_model": config.watch.fallback_model,
        "is_true_hot_issue": importance >= 0.65,
        "importance_score_adjusted": round(importance, 3),
        "momentum_score_adjusted": round(momentum, 3),
        "heat_level": heat,
        "judgment_reason": f"heuristic fallback for '{title[:80]}'",
        "official_signal_importance": "official company signal" if primary_company_tag else "non-official or analysis source",
        "community_reaction_state": "reaction observed" if unique_source_count > 1 else "little/no reaction yet",
        "should_alert_now": importance >= config.watch.importance_alert_threshold or momentum >= config.watch.momentum_alert_threshold,
    }


def _codex_judgment(config: PipelineConfig, *, title: str, primary_company_tag: str | None, signal_count: int, unique_source_count: int, engagement_score: float, reaction_score: float, content_context: str | None = None) -> dict | None:
    codex_path = shutil.which("codex")
    if not codex_path:
        return None
    template = {
        "task": "judge-hot-issue",
        "title": title,
        "primary_company_tag": primary_company_tag,
        "signal_count": signal_count,
        "unique_source_count": unique_source_count,
        "engagement_score": engagement_score,
        "reaction_score": reaction_score,
        "source_content_excerpt": content_context,
        "rules": [
            "read the source_content_excerpt first; judge substance before metrics",
            "explain why this matters in terms of product, research, infrastructure, market, or policy impact",
            "include a concise content summary, not only engagement/reaction counts",
            "official company posts can be hot issues by themselves",
            "community reaction is a separate lens, not the same event as origin",
            "X/Twitter is a core hotness signal surface when available",
            "return strict JSON only",
            "avoid generic PR noise",
        ],
        "required_output_keys": [
            "is_true_hot_issue",
            "importance_score_adjusted",
            "momentum_score_adjusted",
            "heat_level",
            "judgment_reason",
            "content_summary",
            "why_it_matters",
            "official_signal_importance",
            "community_reaction_state",
            "should_alert_now",
        ],
    }
    prompt = (
        "You are judging whether this is a real AI/Cloud hot issue. "
        "Return exactly one JSON object and nothing else.\n\n"
        f"INPUT_JSON:\n{json.dumps(template, ensure_ascii=False)}"
    )
    try:
        completed = subprocess.run(
            [codex_path, "exec", prompt],
            cwd=config.workspace_root,
            capture_output=True,
            text=True,
            timeout=90,
            check=True,
        )
        raw = (completed.stdout or "").strip()
        if not raw:
            return None
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        data = json.loads(raw[start:end + 1])
        data.setdefault("engine", "codex-cli")
        data.setdefault("configured_model", config.watch.adjudicator_model)
        data.setdefault("fallback_model", config.watch.fallback_model)
        return data
    except Exception:
        return None


def fetch_source_items(source: WatchSource, fetch_text=_fetch_text, fetch_json=_fetch_json) -> list[dict]:
    if source.ingest_strategy in {"rss", "atom"}:
        items = _parse_rss_or_atom(fetch_text(source.feed_url or source.base_url), source)
        if _looks_like_x_source(source):
            return [_enrich_x_item(source, item, fetch_text) for item in items[:1]]
        return _enrich_items_with_bounded_search_fallback(items[:10], fetch_text)
    if source.ingest_strategy == "api" and source.source_id == "hackernews-topstories":
        return _fetch_hackernews(source, fetch_json=fetch_json, fetch_text=fetch_text)
    if source.ingest_strategy == "html":
        return _enrich_items_with_bounded_search_fallback(_parse_html_listing(fetch_text(source.html_list_url or source.base_url), source), fetch_text)
    target_url = source.feed_url or source.html_list_url or source.base_url
    return [{"title": source.display_name, "url": target_url, "summary_text": f"Fetched from {target_url}", "published_at": _utc_now().isoformat()}]


def load_watch_sources(config: PipelineConfig) -> list[WatchSource]:
    base = config.watch.source_config_dir
    if not base.exists():
        return []
    sources: list[WatchSource] = []
    for path in sorted(base.rglob("*.yaml")):
        if path.name == "MANIFEST.yaml":
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        sources.append(
            WatchSource(
                source_id=str(raw["source_id"]),
                display_name=str(raw["display_name"]),
                company_tag=(str(raw["company_tag"]) if raw.get("company_tag") else None),
                source_class=(str(raw["source_class"]) if raw.get("source_class") else None),
                source_role=str(raw["source_role"]),
                source_type=str(raw["source_type"]),
                ingest_strategy=str(raw["ingest_strategy"]),
                base_url=str(raw["base_url"]),
                feed_url=(str(raw["feed_url"]) if raw.get("feed_url") else None),
                html_list_url=(str(raw["html_list_url"]) if raw.get("html_list_url") else None),
                poll_minutes=int(raw.get("poll_minutes", config.watch.default_poll_minutes)),
                enabled=bool(raw.get("enabled", True)),
                validation_status=(str(raw["validation_status"]) if raw.get("validation_status") else None),
                validation_notes=tuple(str(item) for item in raw.get("validation_notes", [])),
                browser_required=bool(raw.get("browser_required", False)),
                anti_bot_risk=(str(raw["anti_bot_risk"]) if raw.get("anti_bot_risk") else None),
                priority_weight=float(raw.get("priority_weight", 0.0)),
                reaction_weight=float(raw.get("reaction_weight", 0.0)),
                cooldown_minutes=int(raw.get("cooldown_minutes", 60)),
                topic_tags=tuple(str(item) for item in raw.get("topic_tags", [])),
                file_path=path,
            )
        )
    return sources


def sync_watch_sources(config: PipelineConfig) -> dict:
    bootstrap_workspace(config)
    now = _utc_now().isoformat()
    sources = load_watch_sources(config)
    with sqlite3.connect(config.database_path) as conn:
        for source in sources:
            conn.execute(
                """
                INSERT OR REPLACE INTO watch_sources (
                    source_id, display_name, company_tag, source_class, source_role, source_type, ingest_strategy,
                    base_url, feed_url, html_list_url, poll_minutes, enabled, validation_status, validation_notes_json,
                    browser_required, anti_bot_risk, priority_weight, reaction_weight, cooldown_minutes, topic_tags_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          COALESCE((SELECT created_at FROM watch_sources WHERE source_id = ?), ?), ?)
                """,
                (
                    source.source_id,
                    source.display_name,
                    source.company_tag,
                    source.source_class,
                    source.source_role,
                    source.source_type,
                    source.ingest_strategy,
                    source.base_url,
                    source.feed_url,
                    source.html_list_url,
                    source.poll_minutes,
                    int(source.enabled),
                    source.validation_status,
                    json.dumps(list(source.validation_notes), ensure_ascii=False),
                    int(source.browser_required),
                    source.anti_bot_risk,
                    source.priority_weight,
                    source.reaction_weight,
                    source.cooldown_minutes,
                    json.dumps(list(source.topic_tags), ensure_ascii=False),
                    source.source_id,
                    now,
                    now,
                ),
            )
        conn.commit()
    return {"source_count": len(sources), "enabled_count": sum(1 for s in sources if s.enabled), "source_ids": [s.source_id for s in sources]}


def _make_signal_id(source_id: str, item_url: str, title: str) -> str:
    digest = hashlib.sha256(f"{source_id}|{item_url}|{title}".encode()).hexdigest()[:16]
    return f"{source_id}:{digest}"


def collect_watch_signals(config: PipelineConfig, fetcher=None) -> dict:
    bootstrap_workspace(config)
    sync_watch_sources(config)
    now = _utc_now().isoformat()
    fetcher = fetcher or fetch_source_items
    enabled_sources = [s for s in load_watch_sources(config) if s.enabled]
    collected = []
    recency_start = _utc_now() - timedelta(hours=config.watch.recency_hours)
    with sqlite3.connect(config.database_path) as conn:
        for source in enabled_sources:
            try:
                items = fetcher(source)
            except Exception:
                continue
            for item in items:
                published_at = _parse_dt(item.get("published_at")) or now
                try:
                    published_dt = datetime.fromisoformat(published_at)
                except ValueError:
                    published_dt = _utc_now()
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=UTC)
                if published_dt < recency_start:
                    continue
                title = str(item.get("title") or source.display_name)
                url = _canonicalize_url(str(item.get("url") or source.feed_url or source.base_url), base_url=source.base_url)
                signal_id = _make_signal_id(source.source_id, url, title)
                signal_kind = "official-post" if source.source_role == "official-origin" else ("reaction-thread" if source.source_role == "reaction" else "media-post")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO watch_signals (
                        signal_id, source_id, source_type, signal_kind, company_tag, external_id, title, url, author,
                        summary_text, published_at, collected_at, engagement_json, topic_tags_json, entity_tags_json,
                        language, canonical_key, content_hash, raw_payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        signal_id,
                        source.source_id,
                        source.source_type,
                        signal_kind,
                        source.company_tag,
                        item.get("external_id"),
                        title,
                        url,
                        item.get("author"),
                        item.get("summary_text"),
                        published_at,
                        now,
                        json.dumps(item.get("engagement") or {}, ensure_ascii=False),
                        json.dumps(list(source.topic_tags), ensure_ascii=False),
                        json.dumps(([source.company_tag] if source.company_tag else []), ensure_ascii=False),
                        item.get("language"),
                        _normalize_title(title),
                        hashlib.sha256(f"{title}|{url}".encode()).hexdigest(),
                        json.dumps(item, ensure_ascii=False),
                    ),
                )
                collected.append(signal_id)
        conn.commit()
    return {"signal_count": len(collected), "source_count": len(enabled_sources), "signal_ids": collected}


def _find_matching_issue(seen: dict[str, tuple[str, str | None]], title: str, company_tag: str | None, similarity_threshold: float) -> str | None:
    key = _story_key(title, company_tag)
    if key in seen:
        return seen[key][0]
    normalized = _normalize_title(title)
    for seen_key, (issue_id, seen_company) in seen.items():
        same_company = seen_company == company_tag or seen_company is None or company_tag is None
        if not same_company:
            continue
        seen_title = seen_key.split("::", 1)[1]
        if SequenceMatcher(None, normalized, seen_title).ratio() >= similarity_threshold:
            return issue_id
    return None


def build_watch_stories(config: PipelineConfig) -> dict:
    bootstrap_workspace(config)
    created = 0
    recency_start = (_utc_now() - timedelta(hours=config.watch.recency_hours)).isoformat()
    with sqlite3.connect(config.database_path) as conn:
        conn.row_factory = sqlite3.Row
        signals = conn.execute(
            """
            SELECT *
            FROM watch_signals
            WHERE datetime(COALESCE(published_at, collected_at)) >= datetime(?)
            ORDER BY collected_at ASC
            """,
            (recency_start,),
        ).fetchall()
        seen: dict[str, tuple[str, str | None]] = {}
        for row in signals:
            issue_id = _find_matching_issue(seen, row["title"], row["company_tag"], config.watch.story_similarity)
            story_key = _story_key(row["title"], row["company_tag"])
            if issue_id is None:
                issue_id = f"issue:{hashlib.sha256(story_key.encode()).hexdigest()[:16]}"
                seen[story_key] = (issue_id, row["company_tag"])
                conn.execute(
                    """
                    INSERT OR IGNORE INTO watch_issue_stories (
                        issue_id, story_key, canonical_title, canonical_summary, primary_company_tag, topic_ids_json,
                        entity_tags_json, origin_signal_id, origin_kind, first_seen_at, last_seen_at,
                        current_importance_score, current_momentum_score, current_heat_level, report_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'low', 'unseen')
                    """,
                    (
                        issue_id,
                        story_key,
                        row["title"],
                        row["summary_text"],
                        row["company_tag"],
                        row["topic_tags_json"],
                        row["entity_tags_json"],
                        row["signal_id"],
                        "official-origin" if row["signal_kind"] == "official-post" else "mixed-origin",
                        row["collected_at"],
                        row["collected_at"],
                    ),
                )
                created += 1
            role = "origin" if row["signal_kind"] == "official-post" else "reaction"
            conn.execute("INSERT OR IGNORE INTO watch_issue_signals (issue_id, signal_id, role) VALUES (?, ?, ?)", (issue_id, row["signal_id"], role))
            agg = conn.execute(
                """
                SELECT COUNT(*) as signal_count,
                       SUM(CASE WHEN ws.signal_kind = 'official-post' THEN 1 ELSE 0 END) as official_count,
                       COUNT(DISTINCT ws.source_id) as unique_sources,
                       SUM(
                           MAX(
                               COALESCE(json_extract(ws.engagement_json, '$.score'), 0),
                               COALESCE(json_extract(ws.engagement_json, '$.favorite_count'), 0)
                               + COALESCE(json_extract(ws.engagement_json, '$.retweet_count'), 0)
                               + COALESCE(json_extract(ws.engagement_json, '$.quote_count'), 0)
                           )
                       ) as score_sum,
                       SUM(
                           MAX(
                               COALESCE(json_extract(ws.engagement_json, '$.comments'), 0),
                               COALESCE(json_extract(ws.engagement_json, '$.reply_count'), 0)
                               + COALESCE(json_extract(ws.engagement_json, '$.quote_count'), 0)
                           )
                       ) as comments_sum
                FROM watch_issue_signals wis
                JOIN watch_signals ws ON ws.signal_id = wis.signal_id
                WHERE wis.issue_id = ?
                  AND datetime(COALESCE(ws.published_at, ws.collected_at)) >= datetime(?)
                """,
                (issue_id, recency_start),
            ).fetchone()
            signal_count = int(agg["signal_count"] or 0)
            official_count = int(agg["official_count"] or 0)
            community_count = signal_count - official_count
            unique_sources = int(agg["unique_sources"] or 0)
            engagement_score = float(agg["score_sum"] or 0.0)
            reaction_score = float(agg["comments_sum"] or 0.0)
            conn.execute(
                "UPDATE watch_issue_stories SET last_seen_at = ?, canonical_title = COALESCE(canonical_title, ?) WHERE issue_id = ?",
                (row["collected_at"], row["title"], issue_id),
            )
            snapshot_hour = row["collected_at"][:13] + ":00:00+00:00" if "+00:00" in row["collected_at"] else row["collected_at"][:13]
            conn.execute(
                "INSERT OR REPLACE INTO watch_issue_snapshots (snapshot_id, issue_id, snapshot_hour, signal_count, official_signal_count, community_signal_count, unique_source_count, engagement_score, reaction_score, importance_score, momentum_score, heat_level, llm_judgment_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"{issue_id}:{snapshot_hour}",
                    issue_id,
                    snapshot_hour,
                    signal_count,
                    official_count,
                    community_count,
                    unique_sources,
                    engagement_score,
                    reaction_score,
                    0.0,
                    0.0,
                    "low",
                    "{}",
                ),
            )
        conn.commit()
        issue_count = conn.execute(
            "SELECT COUNT(*) FROM watch_issue_stories WHERE datetime(last_seen_at) >= datetime(?)",
            (recency_start,),
        ).fetchone()[0]
    return {"issue_count": issue_count, "created_count": created}


def _calculate_snapshot_momentum(current: sqlite3.Row, previous: sqlite3.Row | None) -> float:
    if previous is None:
        return min(
            1.0,
            max(
                0.0,
                max(0, int(current["unique_source_count"] or 0) - 1) * 0.12
                + (float(current["reaction_score"] or 0.0) / 500.0),
            ),
        )
    delta_sources = max(0, int(current["unique_source_count"] or 0) - int(previous["unique_source_count"] or 0))
    delta_signals = max(0, int(current["signal_count"] or 0) - int(previous["signal_count"] or 0))
    delta_engagement = max(0.0, float(current["engagement_score"] or 0.0) - float(previous["engagement_score"] or 0.0))
    delta_reaction = max(0.0, float(current["reaction_score"] or 0.0) - float(previous["reaction_score"] or 0.0))
    return min(1.0, delta_sources * 0.18 + delta_signals * 0.08 + (delta_engagement / 1500.0) + (delta_reaction / 700.0))


def _normalize_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score < 0:
        return 0.0
    if score > 1.0:
        if score <= 100.0:
            score /= 100.0
        else:
            score = 1.0
    return round(min(1.0, score), 3)


def _should_use_codex_for_issue(row: sqlite3.Row, heuristic: dict, *, rank: int) -> bool:
    if rank >= 6:
        return False
    if int(row["official_signal_count"] or 0) > 0 and (
        int(row["signal_count"] or 0) >= 2
        or int(row["unique_source_count"] or 0) >= 2
        or float(row["engagement_score"] or 0.0) >= 250
        or float(row["reaction_score"] or 0.0) >= 75
    ):
        return True
    if int(row["unique_source_count"] or 0) >= 2:
        return True
    if float(row["engagement_score"] or 0.0) >= 250 or float(row["reaction_score"] or 0.0) >= 75:
        return True
    return bool(heuristic.get("is_true_hot_issue"))


def _judgment_is_alertable(config: PipelineConfig, judgment: dict, *, importance: float, momentum: float) -> bool:
    """Return whether a judged issue should enter the delivered hot-issue report.

    Momentum alone is intentionally insufficient.  Otherwise low-importance
    one-off community links can cross a tiny momentum threshold and get sent as
    "hot issues" even when the judge explicitly marked them as not true hot
    issues.
    """
    if not bool(judgment.get("is_true_hot_issue")):
        return False
    if importance >= config.watch.importance_alert_threshold:
        return True
    return importance >= config.watch.digest_threshold and momentum >= config.watch.momentum_alert_threshold


def _content_context_from_row(row: sqlite3.Row | dict) -> str | None:
    if isinstance(row, dict):
        summary = row.get("origin_summary_text") or row.get("summary_text") or row.get("canonical_summary")
        raw_payload = row.get("origin_raw_payload_json") or row.get("raw_payload_json")
    else:
        keys = set(row.keys())
        summary = row["origin_summary_text"] if "origin_summary_text" in keys else None
        raw_payload = row["origin_raw_payload_json"] if "origin_raw_payload_json" in keys else None
    content_excerpt = None
    if raw_payload:
        try:
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            content_excerpt = payload.get("content_excerpt") if isinstance(payload, dict) else None
        except (TypeError, json.JSONDecodeError):
            content_excerpt = None
    return _compact_excerpt("\n".join(part for part in [str(summary or ""), str(content_excerpt or "")] if part.strip()), limit=1400)


def _hydrate_issue_content_if_missing(conn: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    context = _content_context_from_row(row)
    if context:
        return context
    title = str(row["canonical_title"] or "").strip()
    url = str(row["origin_url"] or "").strip()
    signal_id = str(row["origin_signal_id"] or "").strip()
    if not title or not url or not signal_id:
        return None
    try:
        enriched = _enrich_item_content({"title": title, "url": url}, _fetch_text, allow_search_fallback=True)
    except Exception:
        return None
    if not enriched.get("content_excerpt"):
        return None
    existing_payload = {}
    raw_payload = row["origin_raw_payload_json"]
    if raw_payload:
        try:
            parsed = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            if isinstance(parsed, dict):
                existing_payload = parsed
        except (TypeError, json.JSONDecodeError):
            existing_payload = {}
    existing_payload.update({k: v for k, v in enriched.items() if k in {"content_excerpt", "content_source_url"}})
    conn.execute(
        "UPDATE watch_signals SET raw_payload_json = ? WHERE signal_id = ?",
        (json.dumps(existing_payload, ensure_ascii=False), signal_id),
    )
    return _compact_excerpt(str(enriched.get("content_excerpt") or ""), limit=1400)


def judge_watch_issues(config: PipelineConfig) -> dict:
    bootstrap_workspace(config)
    judged = []
    recency_start = (_utc_now() - timedelta(hours=config.watch.recency_hours)).isoformat()
    with sqlite3.connect(config.database_path) as conn:
        conn.row_factory = sqlite3.Row
        issues = conn.execute(
            """
            SELECT wis.issue_id,
                   wis.canonical_title,
                   wis.primary_company_tag,
                   wis.origin_signal_id,
                   latest.snapshot_hour,
                   latest.signal_count,
                   latest.official_signal_count,
                   latest.community_signal_count,
                   latest.unique_source_count,
                   latest.engagement_score,
                   latest.reaction_score,
                   ws.url AS origin_url,
                   ws.summary_text AS origin_summary_text,
                   ws.raw_payload_json AS origin_raw_payload_json
            FROM watch_issue_stories wis
            JOIN watch_issue_snapshots latest
              ON latest.issue_id = wis.issue_id
             AND latest.snapshot_hour = (
                SELECT MAX(snapshot_hour)
                FROM watch_issue_snapshots inner_snap
                WHERE inner_snap.issue_id = wis.issue_id
             )
            LEFT JOIN watch_signals ws ON ws.signal_id = wis.origin_signal_id
            WHERE datetime(wis.last_seen_at) >= datetime(?)
            ORDER BY latest.official_signal_count DESC,
                     latest.unique_source_count DESC,
                     latest.engagement_score DESC,
                     latest.reaction_score DESC,
                     wis.first_seen_at ASC
            """,
            (recency_start,),
        ).fetchall()
        for rank, row in enumerate(issues):
            snapshots = conn.execute(
                """
                SELECT snapshot_hour, signal_count, official_signal_count, community_signal_count,
                       unique_source_count, engagement_score, reaction_score
                FROM watch_issue_snapshots
                WHERE issue_id = ?
                ORDER BY snapshot_hour DESC
                LIMIT 2
                """,
                (row["issue_id"],),
            ).fetchall()
            current_snapshot = snapshots[0]
            previous_snapshot = snapshots[1] if len(snapshots) > 1 else None
            heuristic = _heuristic_judgment(
                config,
                title=row["canonical_title"],
                primary_company_tag=row["primary_company_tag"],
                signal_count=int(current_snapshot["signal_count"] or 0),
                unique_source_count=int(current_snapshot["unique_source_count"] or 0),
                engagement_score=float(current_snapshot["engagement_score"] or 0.0),
                reaction_score=float(current_snapshot["reaction_score"] or 0.0),
            )
            heuristic["momentum_score_adjusted"] = round(
                max(
                    float(heuristic.get("momentum_score_adjusted", 0.0)),
                    _calculate_snapshot_momentum(current_snapshot, previous_snapshot),
                ),
                3,
            )
            heuristic["should_alert_now"] = _judgment_is_alertable(
                config,
                heuristic,
                importance=float(heuristic["importance_score_adjusted"]),
                momentum=float(heuristic["momentum_score_adjusted"]),
            )
            content_context = _hydrate_issue_content_if_missing(conn, row)
            judgment = heuristic
            if _should_use_codex_for_issue(row, heuristic, rank=rank):
                judgment = _codex_judgment(
                    config,
                    title=row["canonical_title"],
                    primary_company_tag=row["primary_company_tag"],
                    signal_count=int(current_snapshot["signal_count"] or 0),
                    unique_source_count=int(current_snapshot["unique_source_count"] or 0),
                    engagement_score=float(current_snapshot["engagement_score"] or 0.0),
                    reaction_score=float(current_snapshot["reaction_score"] or 0.0),
                    content_context=content_context,
                ) or heuristic
                judgment["momentum_score_adjusted"] = round(
                    max(
                        float(judgment.get("momentum_score_adjusted", 0.0)),
                        float(heuristic["momentum_score_adjusted"]),
                    ),
                    3,
                )
                judgment["should_alert_now"] = _judgment_is_alertable(
                    config,
                    judgment,
                    importance=float(judgment.get("importance_score_adjusted", heuristic["importance_score_adjusted"])),
                    momentum=float(judgment.get("momentum_score_adjusted", heuristic["momentum_score_adjusted"])),
                )
            importance = _normalize_score(judgment.get("importance_score_adjusted", heuristic["importance_score_adjusted"]))
            momentum = _normalize_score(judgment.get("momentum_score_adjusted", heuristic["momentum_score_adjusted"]))
            heat = str(judgment.get("heat_level", heuristic["heat_level"]))
            status = "watching" if _judgment_is_alertable(
                config,
                judgment,
                importance=importance,
                momentum=momentum,
            ) else "unseen"
            conn.execute(
                "UPDATE watch_issue_stories SET current_importance_score = ?, current_momentum_score = ?, current_heat_level = ?, report_status = ? WHERE issue_id = ?",
                (importance, momentum, heat, status, row["issue_id"]),
            )
            conn.execute(
                "UPDATE watch_issue_snapshots SET importance_score = ?, momentum_score = ?, heat_level = ?, llm_judgment_json = ? WHERE issue_id = ? AND snapshot_hour = ?",
                (importance, momentum, heat, json.dumps(judgment, ensure_ascii=False), row["issue_id"], row["snapshot_hour"]),
            )
            judged.append(row["issue_id"])
        conn.commit()
    return {"judged_count": len(judged), "issue_ids": judged}


def _external_hot_issue_window_key(now: datetime | None = None) -> str:
    current = now or _utc_now()
    current = (current if current.tzinfo else current.replace(tzinfo=UTC)).astimezone(UTC)
    kst = current + timedelta(hours=9)
    window_end = kst.date() + (timedelta(days=1) if kst.hour >= 19 else timedelta(days=0))
    return window_end.isoformat()


def _parse_watch_report_issues(report_text: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in report_text.splitlines():
        heading = re.match(r"^#{2,3}\s+\d+\.\s+(.+?)\s*$", line)
        if heading:
            if current:
                current["key"] = _canonical_issue_key(current.get("origin"), current.get("title"))
                issues.append(current)
            current = {"title": heading.group(1).strip()}
            continue
        if current is None:
            continue
        if line.startswith("- origin:"):
            current["origin"] = line.split(":", 1)[1].strip()
        elif line.startswith("**출처:**"):
            current["origin"] = line.split(":**", 1)[1].strip()
        elif line.startswith("- company:"):
            current["company"] = line.split(":", 1)[1].strip()
        elif line.startswith("**분류:**"):
            current["company"] = line.split(":**", 1)[1].strip().split("·", 1)[0].strip()
        elif line.startswith("- importance:"):
            current["score"] = line[2:].strip()
        elif line.startswith("**관심도:**"):
            current["score"] = line.strip()
        elif line.startswith("**왜 이슈인가:**"):
            current["reason"] = line.split(":**", 1)[1].strip()
        elif line.startswith("**왜 중요한가:**"):
            current["reason"] = line.split(":**", 1)[1].strip()
        elif line.startswith("**내용 요약:**"):
            current["summary"] = line.split(":**", 1)[1].strip()
    if current:
        current["key"] = _canonical_issue_key(current.get("origin"), current.get("title"))
        issues.append(current)
    return [issue for issue in issues if issue.get("key")]


def _format_hot_issue_score(score: str) -> str:
    if score.startswith("**관심도:**"):
        return score
    match = re.search(r"importance:\s*([0-9.]+)\s*\|\s*momentum:\s*([0-9.]+)", score)
    if match:
        return f"**관심도:** 중요도 **{match.group(1)}** · 모멘텀 **{match.group(2)}**"
    return f"**관심도:** {score}"


def _format_issue_reason(issue: dict | sqlite3.Row) -> str:
    if isinstance(issue, dict):
        title = str(issue.get("title") or issue.get("canonical_title") or "이 이슈")
        company = issue.get("company") or issue.get("primary_company_tag")
        signal_count = issue.get("signal_count")
        official_count = issue.get("official_signal_count")
        unique_sources = issue.get("unique_source_count")
        engagement = issue.get("engagement_score")
        reaction = issue.get("reaction_score")
        judgment_json = issue.get("llm_judgment_json")
    else:
        title = str(issue["canonical_title"] or "이 이슈")
        company = issue["primary_company_tag"]
        signal_count = issue["signal_count"]
        official_count = issue["official_signal_count"]
        unique_sources = issue["unique_source_count"]
        engagement = issue["engagement_score"]
        reaction = issue["reaction_score"]
        judgment_json = issue["llm_judgment_json"]
    try:
        judgment = json.loads(judgment_json or "{}") if isinstance(judgment_json, str) else (judgment_json or {})
    except (TypeError, json.JSONDecodeError):
        judgment = {}
    reason = str(judgment.get("judgment_reason") or "").strip()
    if reason and not reason.startswith("heuristic fallback for"):
        return reason
    content_summary = str(judgment.get("content_summary") or "").strip()
    if not content_summary:
        try:
            content_summary = _content_context_from_row(issue) or ""
        except (TypeError, KeyError):
            content_summary = ""
    if content_summary:
        trimmed = content_summary[:260].rstrip() + ("…" if len(content_summary) > 260 else "")
        return f"본문상 핵심은 다음과 같습니다: {trimmed} 이 내용은 제품 전략, 연구/안전, 인프라, 시장 구조, 정책 리스크 중 하나 이상에 직접 영향을 줄 수 있어 추적 가치가 있습니다."
    facts = []
    if company and str(company) != "unknown":
        facts.append(f"{company} 관련 공식/주요 신호")
    if int(official_count or 0) > 0:
        facts.append(f"공식 신호 {int(official_count or 0)}건")
    if int(unique_sources or 0) > 1:
        facts.append(f"복수 출처 {int(unique_sources or 0)}곳에서 관측")
    if float(engagement or 0.0) > 0 or float(reaction or 0.0) > 0:
        facts.append(f"참여 {float(engagement or 0.0):.0f} · 리액션 {float(reaction or 0.0):.0f}")
    if not facts:
        facts.append(f"최근 관측 신호 {int(signal_count or 0)}건")
    return f"{title[:80]} — " + ", ".join(facts) + " 때문에 AI/클라우드/반도체/주요 테크 흐름에서 추적할 가치가 있습니다."


def _format_issue_content_summary(issue: dict | sqlite3.Row) -> str:
    try:
        judgment_json = issue.get("llm_judgment_json") if isinstance(issue, dict) else issue["llm_judgment_json"]
        judgment = json.loads(judgment_json or "{}") if isinstance(judgment_json, str) else (judgment_json or {})
    except (TypeError, KeyError, json.JSONDecodeError):
        judgment = {}
    summary = str(judgment.get("content_summary") or "").strip()
    if summary:
        return summary
    context = _content_context_from_row(issue)
    if context:
        return context[:360].rstrip() + ("…" if len(context) > 360 else "")
    return "원문 요약을 확보하지 못했습니다. 제목과 출처 메타데이터만으로 추적 중입니다."


def _format_issue_why_it_matters(issue: dict | sqlite3.Row) -> str:
    try:
        judgment_json = issue.get("llm_judgment_json") if isinstance(issue, dict) else issue["llm_judgment_json"]
        judgment = json.loads(judgment_json or "{}") if isinstance(judgment_json, str) else (judgment_json or {})
    except (TypeError, KeyError, json.JSONDecodeError):
        judgment = {}
    why = str(judgment.get("why_it_matters") or "").strip()
    if why:
        return why
    return _format_issue_reason(issue)


def _read_external_hot_issue_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"window_end_day_kst": None, "seen_issue_keys": [], "day_issue_records": []}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"window_end_day_kst": None, "seen_issue_keys": [], "day_issue_records": []}
    state.setdefault("seen_issue_keys", [])
    state.setdefault("day_issue_records", [])
    return state


def _write_external_hot_issue_state_atomic(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, state_path)


def generate_external_hot_issue_alert(report_path: Path, state_path: Path, now: datetime | None = None) -> dict:
    report_text = report_path.read_text(encoding="utf-8")
    issues = _parse_watch_report_issues(report_text)
    window_key = _external_hot_issue_window_key(now)
    state = _read_external_hot_issue_state(state_path)
    state_window = state.get("window_end_day_kst")
    if state_window is None or str(state_window) < window_key:
        state = {"window_end_day_kst": window_key, "seen_issue_keys": [], "day_issue_records": []}
    elif str(state_window) > window_key:
        window_key = str(state_window)

    seen = set(str(key) for key in state.get("seen_issue_keys", []))
    new_issues = [issue for issue in issues if issue["key"] not in seen]
    for issue in new_issues:
        seen.add(issue["key"])
        state.setdefault("day_issue_records", []).append(
            {
                "key": issue["key"],
                "title": issue.get("title"),
                "origin": issue.get("origin"),
                "reported_at": (now or _utc_now()).isoformat(),
                "window_end_day_kst": window_key,
            }
        )
    state["window_end_day_kst"] = window_key
    state["seen_issue_keys"] = sorted(seen)
    _write_external_hot_issue_state_atomic(state_path, state)

    if not new_issues:
        message_text = "[SILENT]"
    else:
        lines = [
            "## 🔥 핫이슈 업데이트",
            "",
            f"**기준 창:** {window_key} KST",
            f"**신규 이슈:** {len(new_issues)}건",
            "",
        ]
        for index, issue in enumerate(new_issues, start=1):
            lines.append(f"### {index}. {issue.get('title', '제목 없음')}")
            if issue.get("score"):
                lines.append(_format_hot_issue_score(issue["score"]))
            if issue.get("summary"):
                lines.append(f"**내용 요약:** {issue['summary']}")
            if issue.get("reason"):
                lines.append(f"**왜 중요한가:** {issue['reason']}")
            if issue.get("origin"):
                lines.append(f"**출처:** {issue['origin']}")
            lines.append("")
        message_text = "\n".join(lines).strip()

    return {
        "message_text": message_text,
        "new_count": len(new_issues),
        "seen_count": len(seen),
        "window_end_day_kst": window_key,
    }


def _news_center_fallback_report(config: PipelineConfig, *, generated_at: str) -> tuple[str, list[str], dict | None]:
    taxonomy_path = config.workspace_root / "config/personal-radar/naver-news-taxonomy.yaml"
    if not taxonomy_path.exists():
        return "[SILENT]", [], None
    try:
        result = collect_news_center(
            taxonomy_path=taxonomy_path,
            output_dir=config.workspace_root / "data/news-center",
            wiki_root=config.wiki_root,
            per_source_limit=1,
        )
    except Exception as exc:  # public news fallback must not break the hot-issues job
        return "[SILENT]", [], {"fallback_error": str(exc)}

    news_md = str(result.get("news_markdown") or "").strip()
    item_count = int(result.get("item_count") or 0)
    if item_count <= 0 or not news_md:
        return "[SILENT]", [], result

    lines = [
        "## 📰 뉴스 센터 업데이트",
        "",
        f"**생성 시각:** {generated_at}",
        "**상태:** 고임계값 핫이슈는 없지만, 네이버/구글 뉴스 기반 일반 브리핑을 보강했습니다.",
        f"**수집 기사:** {item_count}건 · **수집 오류:** {int(result.get('error_count') or 0)}건",
        "",
    ]
    body_lines = [line for line in news_md.splitlines() if line.strip()]
    # Keep the hourly Discord message compact; full markdown/json artifacts are persisted.
    lines.extend(body_lines[:36])
    lines.extend(["", "_전체 뉴스 원문/근거는 Jarvis News Center 아티팩트에 저장했습니다._"])
    issue_ids = [f"news-center:{result.get('artifact_path')}"]
    return "\n".join(lines).strip() + "\n", issue_ids, result


def generate_watch_report(config: PipelineConfig, report_kind: str = "hourly-hot-issues") -> dict:
    bootstrap_workspace(config)
    reports_dir = config.watch.snapshot_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now().isoformat()
    date_key = generated_at.replace(":", "").replace("-", "")
    artifact_path = reports_dir / f"{report_kind}-{date_key}.md"
    recency_start = (_utc_now() - timedelta(hours=config.watch.recency_hours)).isoformat()
    importance_threshold = config.watch.importance_alert_threshold if report_kind == "hourly-hot-issues" else config.watch.digest_threshold
    momentum_threshold = config.watch.momentum_alert_threshold
    with sqlite3.connect(config.database_path) as conn:
        conn.row_factory = sqlite3.Row
        issues = conn.execute(
            """
            SELECT wis.issue_id,
                   wis.canonical_title,
                   wis.primary_company_tag,
                   wis.current_importance_score,
                   wis.current_momentum_score,
                   wis.current_heat_level,
                   latest.signal_count,
                   latest.official_signal_count,
                   latest.community_signal_count,
                   latest.unique_source_count,
                   latest.engagement_score,
                   latest.reaction_score,
                   latest.llm_judgment_json,
                   ws.url AS origin_url,
                   ws.summary_text AS origin_summary_text,
                   ws.raw_payload_json AS origin_raw_payload_json
            FROM watch_issue_stories wis
            JOIN watch_issue_snapshots latest
              ON latest.issue_id = wis.issue_id
             AND latest.snapshot_hour = (
                SELECT MAX(snapshot_hour)
                FROM watch_issue_snapshots inner_snap
                WHERE inner_snap.issue_id = wis.issue_id
             )
            LEFT JOIN watch_signals ws ON ws.signal_id = wis.origin_signal_id
            WHERE datetime(wis.last_seen_at) >= datetime(?)
              AND wis.report_status = 'watching'
              AND (
                wis.current_importance_score >= ?
                OR (wis.current_importance_score >= ? AND wis.current_momentum_score >= ?)
              )
            ORDER BY wis.current_importance_score DESC,
                     wis.current_momentum_score DESC,
                     latest.unique_source_count DESC,
                     latest.engagement_score DESC
            LIMIT 8
            """,
            (recency_start, importance_threshold, config.watch.digest_threshold, momentum_threshold),
        ).fetchall()
        if not issues:
            if report_kind == "hourly-hot-issues":
                text, issue_ids, _ = _news_center_fallback_report(config, generated_at=generated_at)
            else:
                text = "[SILENT]"
                issue_ids = []
        else:
            lines = [
                "## 🔥 핫이슈 업데이트",
                "",
                f"**생성 시각:** {generated_at}",
                f"**신규 이슈:** {len(issues)}건",
                "",
            ]
            issue_ids = []
            for index, row in enumerate(issues, start=1):
                issue_ids.append(row["issue_id"])
                lines.extend(
                    [
                        f"### {index}. {row['canonical_title']}",
                        f"**분류:** {row['primary_company_tag'] or 'unknown'} · **열기:** {row['current_heat_level']}",
                        f"**관심도:** 중요도 **{row['current_importance_score']:.3f}** · 모멘텀 **{row['current_momentum_score']:.3f}**",
                        f"**내용 요약:** {_format_issue_content_summary(row)}",
                        f"**왜 중요한가:** {_format_issue_why_it_matters(row)}",
                        f"**정량 신호:** 관측 총 {int(row['signal_count'] or 0)} · 공식 {int(row['official_signal_count'] or 0)} · 커뮤니티 {int(row['community_signal_count'] or 0)} · 출처 {int(row['unique_source_count'] or 0)} · 참여 {float(row['engagement_score'] or 0.0):.1f} · 리액션 {float(row['reaction_score'] or 0.0):.1f}",
                        f"**출처:** {row['origin_url'] or 'n/a'}",
                        "",
                    ]
                )
            text = "\n".join(lines).strip() + "\n"
        artifact_path.write_text(text, encoding="utf-8")
        conn.execute(
            "INSERT OR REPLACE INTO watch_reports (report_id, generated_at, report_kind, issue_ids_json, artifact_file, delivered_channel) VALUES (?, ?, ?, ?, ?, ?)",
            (f"{report_kind}:{date_key}", generated_at, report_kind, json.dumps(issue_ids, ensure_ascii=False), str(artifact_path), config.deliver_channel),
        )
        conn.commit()
    return {"artifact_path": artifact_path, "report_kind": report_kind, "issue_count": len(issue_ids), "message_text": text}


def run_watch_cycle(config: PipelineConfig) -> dict:
    sync_result = sync_watch_sources(config)
    collect_result = collect_watch_signals(config)
    build_result = build_watch_stories(config)
    judge_result = judge_watch_issues(config)
    report_result = generate_watch_report(config, report_kind="hourly-hot-issues")
    return {
        "sync": sync_result,
        "collect": collect_result,
        "build": build_result,
        "judge": judge_result,
        "report": report_result,
    }
