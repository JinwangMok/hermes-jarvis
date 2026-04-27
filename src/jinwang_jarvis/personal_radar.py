from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import re

import requests
import yaml


@dataclass(frozen=True)
class RadarSource:
    source_id: str
    display_name: str
    url: str
    owner: str
    source_role: str
    domain: str
    authority_level: str
    access_method: str
    poll_minutes: int
    reliability_score: float
    coverage_score: float
    freshness_score: float
    reason_for_inclusion: str
    known_limitations: str
    wiki_destination: str
    reachability_probe: str | None = None
    discovery_urls: tuple[str, ...] = ()
    priority_queries: tuple[str, ...] = ()

    @property
    def composite_score(self) -> float:
        return round((self.reliability_score * 0.4) + (self.coverage_score * 0.35) + (self.freshness_score * 0.25), 3)


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_personal_radar_sources(registry_dir: Path) -> list[RadarSource]:
    registry = _load_yaml(registry_dir / "source-registry.yaml")
    required = set(registry.get("required_fields", []))
    sources: list[RadarSource] = []
    for raw in registry.get("sources", []):
        missing = sorted(required - set(raw))
        if missing:
            raise ValueError(f"{raw.get('source_id', '<unknown>')} missing required fields: {missing}")
        sources.append(
            RadarSource(
                source_id=str(raw["source_id"]),
                display_name=str(raw["display_name"]),
                url=str(raw["url"]),
                owner=str(raw["owner"]),
                source_role=str(raw["source_role"]),
                domain=str(raw["domain"]),
                authority_level=str(raw["authority_level"]),
                access_method=str(raw["access_method"]),
                poll_minutes=int(raw["poll_minutes"]),
                reliability_score=float(raw["reliability_score"]),
                coverage_score=float(raw["coverage_score"]),
                freshness_score=float(raw["freshness_score"]),
                reason_for_inclusion=str(raw["reason_for_inclusion"]),
                known_limitations=str(raw["known_limitations"]),
                wiki_destination=str(raw["wiki_destination"]),
                reachability_probe=(str(raw["reachability_probe"]) if raw.get("reachability_probe") else None),
                discovery_urls=tuple(str(url) for url in raw.get("discovery_urls", [])),
                priority_queries=tuple(str(query) for query in raw.get("priority_queries", [])),
            )
        )
    return sorted(sources, key=lambda s: (-s.composite_score, s.source_id))


def load_personal_radar_taxonomies(registry_dir: Path) -> dict[str, Any]:
    return {
        "government_structure": _load_yaml(registry_dir / "government-structure.yaml"),
        "naver_news_taxonomy": _load_yaml(registry_dir / "naver-news-taxonomy.yaml"),
        "follow_up_workflow": _load_yaml(registry_dir / "follow-up-workflow.yaml"),
        "x_graph_seeds": _load_yaml(registry_dir / "x-graph-seeds.yaml"),
    }


def build_personal_radar_source_audit(registry_dir: Path) -> dict[str, Any]:
    sources = load_personal_radar_sources(registry_dir)
    taxonomies = load_personal_radar_taxonomies(registry_dir)
    domains: dict[str, int] = {}
    roles: dict[str, int] = {}
    for source in sources:
        domains[source.domain] = domains.get(source.domain, 0) + 1
        roles[source.source_role] = roles.get(source.source_role, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(sources),
        "domains": dict(sorted(domains.items())),
        "roles": dict(sorted(roles.items())),
        "top_sources": [
            {
                "source_id": source.source_id,
                "display_name": source.display_name,
                "domain": source.domain,
                "source_role": source.source_role,
                "authority_level": source.authority_level,
                "composite_score": source.composite_score,
                "wiki_destination": source.wiki_destination,
            }
            for source in sources[:10]
        ],
        "naver_category_count": len(taxonomies["naver_news_taxonomy"].get("categories", [])),
        "naver_priority_query_count": len(taxonomies["naver_news_taxonomy"].get("priority_queries", [])),
        "x_seed_count": len(taxonomies["x_graph_seeds"].get("nodes", [])),
        "follow_up_statuses": taxonomies["follow_up_workflow"].get("statuses", []),
    }


def _http_probe(url: str, *, timeout: int = 15) -> dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JinwangJarvis/1.0)", "Accept-Language": "ko-KR,ko;q=0.9"}
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        return {
            "url": url,
            "final_url": response.url,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "length": len(response.content),
            "ok": 200 <= response.status_code < 400,
        }
    except Exception as exc:  # pragma: no cover - network dependent
        return {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _text_probe(url: str, must_include: tuple[str, ...], *, timeout: int = 25) -> dict[str, Any]:
    probe = _http_probe(url, timeout=timeout)
    if not probe.get("ok"):
        return {**probe, "matched_terms": [], "missing_terms": list(must_include)}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JinwangJarvis/1.0)", "Accept-Language": "ko-KR,ko;q=0.9"}
    try:
        text = requests.get(url, headers=headers, timeout=timeout).text
    except Exception as exc:  # pragma: no cover - network dependent
        return {**probe, "ok": False, "error": f"{type(exc).__name__}: {exc}", "matched_terms": [], "missing_terms": list(must_include)}
    compact = re.sub(r"\\s+", " ", text)
    matched = [term for term in must_include if term in compact]
    return {**probe, "matched_terms": matched, "missing_terms": [term for term in must_include if term not in matched], "text_excerpt": compact[:500]}


def verify_personal_radar_coverage(registry_dir: Path, *, live: bool = True) -> dict[str, Any]:
    sources = {source.source_id: source for source in load_personal_radar_sources(registry_dir)}
    failures: list[str] = []
    warnings: list[str] = []

    bokjiro = sources.get("bokjiro")
    if not bokjiro:
        failures.append("missing source_id=bokjiro")
    else:
        bokjiro_urls = "\n".join((bokjiro.url, *bokjiro.discovery_urls))
        if "/ssis-tbu/index.do" not in bokjiro_urls:
            failures.append("bokjiro must include the reachable SPA entry /ssis-tbu/index.do")
        if "selectTwzzIntgSearchServiceSearch.do" not in bokjiro_urls:
            failures.append("bokjiro must include the 복지서비스 search endpoint discovered from Main.clx.js")
        if bokjiro.access_method == "browser-or-manual":
            failures.append("bokjiro access_method must not stop at browser-or-manual; record endpoint/API fallback")

    iris = sources.get("iris")
    if not iris:
        failures.append("missing source_id=iris")
    else:
        iris_queries = "\n".join(iris.priority_queries)
        for term in ["AI 기반 대학 과학기술 혁신사업", "중앙거점", "AI4S&T"]:
            if term not in iris_queries:
                failures.append(f"iris priority_queries missing {term!r}")

    live_probes: list[dict[str, Any]] = []
    if live:
        if bokjiro:
            for url in (bokjiro.url, *bokjiro.discovery_urls[:2]):
                live_probes.append(_http_probe(url))
        for url, terms in [
            ("https://www.iris.go.kr/contents/retrieveBsnsAncmView.do?ancmId=020525&bsnsYyDetail=2026&sorgnBsnsCd=S051500&bsnsAncmSn=1&chngRcveDeFro=2026/04/28&chngRcveDeTo=2026/05/12", ("AI 기반 대학 과학기술 혁신사업", "중앙거점")),
            ("https://www.iris.go.kr/contents/retrieveBsnsAncmView.do?ancmId=020526&bsnsYyDetail=2026&sorgnBsnsCd=S051517&bsnsAncmSn=1&chngRcveDeFro=2026/05/07&chngRcveDeTo=2026/05/22", ("AI 기반 대학 과학기술 혁신사업", "AI4S&T")),
        ]:
            probe = _text_probe(url, terms)
            live_probes.append(probe)
            if probe.get("missing_terms"):
                warnings.append(f"IRIS live probe missing terms for {url}: {probe.get('missing_terms')}")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "live_probes": live_probes,
    }


def generate_personal_radar_coverage_verification(registry_dir: Path, output_dir: Path, *, live: bool = True) -> dict[str, Any]:
    result = verify_personal_radar_coverage(registry_dir, live=live)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"personal-radar-coverage-verification-{stamp}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**result, "json_path": json_path}


def render_personal_radar_source_report(audit: dict[str, Any]) -> str:
    lines = [
        "---",
        "generated: true",
        "authority: generated",
        "canonical: false",
        "generator: jinwang-jarvis-personal-radar",
        "allowed_use: triage_only",
        "---",
        "",
        "# Personal Radar Source Audit",
        "",
        f"Generated at: `{audit['generated_at']}`",
        "",
        f"- Source count: **{audit['source_count']}**",
        f"- Naver categories: **{audit['naver_category_count']}**",
        f"- Naver priority queries: **{audit['naver_priority_query_count']}**",
        f"- X graph seed nodes: **{audit['x_seed_count']}**",
        "",
        "## Domains",
        "",
    ]
    for domain, count in audit["domains"].items():
        lines.append(f"- `{domain}`: {count}")
    lines.extend(["", "## Source Roles", ""])
    for role, count in audit["roles"].items():
        lines.append(f"- `{role}`: {count}")
    lines.extend(["", "## Top Sources", ""])
    for source in audit["top_sources"]:
        lines.append(
            f"- **{source['display_name']}** (`{source['source_id']}`) — "
            f"{source['domain']} / {source['source_role']} / score {source['composite_score']} → `{source['wiki_destination']}`"
        )
    lines.extend(["", "## Follow-up Statuses", "", ", ".join(f"`{s}`" for s in audit["follow_up_statuses"]), ""])
    return "\n".join(lines)


def generate_personal_radar_source_audit(registry_dir: Path, output_dir: Path) -> dict[str, Any]:
    audit = build_personal_radar_source_audit(registry_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"personal-radar-source-audit-{stamp}.json"
    md_path = output_dir / f"personal-radar-source-audit-{stamp}.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_personal_radar_source_report(audit), encoding="utf-8")
    return {**audit, "artifact_path": md_path, "json_path": json_path}
