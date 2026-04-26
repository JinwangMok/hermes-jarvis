from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

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
