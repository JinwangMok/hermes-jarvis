from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "personal-radar"


def load_yaml(name):
    return yaml.safe_load((CFG / name).read_text(encoding="utf-8"))


def test_personal_radar_score_gate_is_at_or_below_threshold():
    text = (ROOT / "docs" / "design" / "personal-intelligence-radar-coverage-gate.md").read_text(encoding="utf-8")
    assert "combined_score: 0.05" in text
    assert "implementation_allowed: true" in text
    for requirement in [
        "Korean government structure",
        "latest budget/policy",
        "Naver News",
        "X researcher/CEO graph",
        "Wiki storage",
    ]:
        assert requirement in text


def test_source_registry_has_required_personal_radar_fields_and_domains():
    registry = load_yaml("source-registry.yaml")
    required = set(registry["required_fields"])
    expected_domains = {
        "budget-policy",
        "cross-government-policy",
        "research-grants",
        "ict-ai-cloud-rnd",
        "ai-cloud-sw-industry",
        "university-research",
        "startup-support",
        "youth-policy",
        "welfare-benefits",
        "housing-welfare",
        "housing-subscription",
        "korea-news-taxonomy-agenda",
    }
    domains = {source["domain"] for source in registry["sources"]}
    assert expected_domains <= domains
    assert len(registry["sources"]) >= 15
    for source in registry["sources"]:
        assert required <= set(source)
        assert 0 <= float(source["reliability_score"]) <= 1
        assert 0 <= float(source["coverage_score"]) <= 1
        assert 0 <= float(source["freshness_score"]) <= 1


def test_government_structure_normalizes_core_aliases():
    gov = load_yaml("government-structure.yaml")
    aliases = gov["normalization_tests"]
    assert aliases["과기정통부"] == "msit"
    assert aliases["MSIT"] == "msit"
    assert aliases["산자부"] == "motie"
    assert aliases["국토부"] == "molit"
    ministry_ids = {m["id"] for m in gov["ministries"]}
    assert {"moef", "msit", "motie", "mss", "molit", "mohw", "moe"} <= ministry_ids


def test_naver_taxonomy_and_priority_queries_exist():
    naver = load_yaml("naver-news-taxonomy.yaml")
    cats = {c["internal_category"] for c in naver["categories"]}
    assert {"politics", "economy", "society", "it-science", "world"} <= cats
    assert len(naver["priority_queries"]) >= 10
    assert naver["collection_policy"] == "metadata_only_no_full_text"


def test_x_graph_seed_has_minimum_required_nodes_and_policy():
    graph = load_yaml("x-graph-seeds.yaml")
    nodes = graph["nodes"]
    ids = {n["id"] for n in nodes}
    assert {"andrej-karpathy", "yann-lecun", "sam-altman", "jensen-huang", "satya-nadella"} <= ids
    assert len(nodes) >= 10
    assert "X is supporting evidence only until provenance is reliable" in graph["phase0_acceptance"]


def test_followup_workflow_prevents_overclaiming_eligibility():
    workflow = load_yaml("follow-up-workflow.yaml")
    assert "missing_user_info" in workflow["required_fields"]
    assert "신청 가능 확정" in workflow["eligibility_language"]["forbidden_without_official_confirmation"]
    assert {"new", "watching", "action_recommended", "expired"} <= set(workflow["statuses"])


def test_personal_radar_source_audit_builds_generated_artifact(tmp_path):
    from jinwang_jarvis.personal_radar import generate_personal_radar_source_audit

    result = generate_personal_radar_source_audit(CFG, tmp_path)
    assert result["source_count"] >= 15
    assert result["naver_category_count"] >= 5
    assert result["x_seed_count"] >= 10
    assert result["artifact_path"].exists()
    text = result["artifact_path"].read_text(encoding="utf-8")
    assert "generated: true" in text
    assert "Personal Radar Source Audit" in text
