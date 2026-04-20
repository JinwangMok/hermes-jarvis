from jinwang_jarvis.classifier import (
    classify_message,
    parse_sender_map_markdown,
    resolve_sender_identity,
)


def test_parse_sender_map_markdown_extracts_roles_and_emails():
    markdown = """
## Current members
- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr
- Research Professor | 박선(Sun Park) | sunpark@smartx.kr
- Ph.D. Student | 목진왕(JinWang Mok) | jinwang@smartx.kr / jinwangmok@gmail.com
- Intern | 권효재 | hyojaekwon@smartx.kr

## User-provided additional identity context
- `jongwon@gist.ac.kr`
"""

    identities = parse_sender_map_markdown(markdown, {"jinwangmok@gmail.com"})

    assert identities["jongwon@smartx.kr"]["role"] == "advisor"
    assert identities["sunpark@smartx.kr"]["role"] == "research-professor"
    assert identities["jinwangmok@gmail.com"]["role"] == "self"
    assert identities["hyojaekwon@smartx.kr"]["role"] == "intern"
    assert identities["jongwon@gist.ac.kr"]["role"] == "advisor"


def test_resolve_sender_identity_uses_exact_match_then_domain_defaults():
    sender_map = {
        "jongwon@smartx.kr": {"email": "jongwon@smartx.kr", "display_name": "김종원", "role": "advisor", "organization": "smartx", "priority_base": 100},
    }

    exact = resolve_sender_identity("jongwon@smartx.kr", sender_map)
    domain = resolve_sender_identity("someone@smartx.kr", sender_map)
    unknown = resolve_sender_identity("person@example.org", sender_map)

    assert exact["role"] == "advisor"
    assert domain["role"] == "external"
    assert domain["organization"] == "smartx.kr"
    assert unknown["role"] == "external"


def test_classify_message_marks_advisor_and_security_routine_labels():
    sender_map = {
        "jongwon@smartx.kr": {"email": "jongwon@smartx.kr", "display_name": "김종원", "role": "advisor", "organization": "smartx", "priority_base": 100},
    }
    message = {
        "message_id": "m1",
        "account": "smartx",
        "folder_kind": "inbox",
        "from_addr": "jongwon@smartx.kr",
        "subject": "Security alert for your account",
    }

    result = classify_message(message, sender_map, work_accounts={"smartx"})
    labels = {entry["label"]: entry for entry in result["labels"]}

    assert result["sender_identity"]["role"] == "advisor"
    assert "advisor-request" in labels
    assert "security-routine" in labels
    assert "work-account" in labels
    assert labels["advisor-request"]["score"] > labels["security-routine"]["score"]


def test_classify_message_marks_ta_and_promotional_reference_labels():
    sender_map = {}
    message = {
        "message_id": "m2",
        "account": "smartx",
        "folder_kind": "inbox",
        "from_addr": "noreply@conference.org",
        "subject": "[TA] conference solution demo and vendor event",
    }

    result = classify_message(message, sender_map)
    labels = {entry["label"] for entry in result["labels"]}

    assert "ta" in labels
    assert "promotional-reference" in labels


def test_advisor_forwarded_intro_material_is_downgraded_to_advisor_fyi():
    sender_map = {
        "jongwon@smartx.kr": {"email": "jongwon@smartx.kr", "display_name": "김종원", "role": "advisor", "organization": "smartx", "priority_base": 100},
    }
    message = {
        "message_id": "m4",
        "account": "smartx",
        "folder_kind": "inbox",
        "from_addr": "jongwon@smartx.kr",
        "subject": "Fwd: VAST Data 소개자료",
    }

    result = classify_message(message, sender_map)
    labels = {entry["label"]: entry for entry in result["labels"]}

    assert "advisor-fyi" in labels
    assert "advisor-request" not in labels


def test_advisor_invitation_is_downgraded_to_advisor_fyi_even_with_meeting_words():
    sender_map = {
        "jongwon@smartx.kr": {"email": "jongwon@smartx.kr", "display_name": "김종원", "role": "advisor", "organization": "smartx", "priority_base": 100},
    }
    message = {
        "message_id": "m5",
        "account": "smartx",
        "folder_kind": "inbox",
        "from_addr": "jongwon@smartx.kr",
        "subject": "초대장] 2026년도 인공지능 챔피언 대회 사업설명회에 여러분을 초대합니다!",
    }

    result = classify_message(message, sender_map)
    labels = {entry["label"]: entry for entry in result["labels"]}

    assert "advisor-fyi" in labels
    assert "advisor-request" not in labels


def test_advisor_report_update_is_downgraded_to_advisor_fyi():
    sender_map = {
        "jongwon@smartx.kr": {"email": "jongwon@smartx.kr", "display_name": "김종원", "role": "advisor", "organization": "smartx", "priority_base": 100},
    }
    message = {
        "message_id": "m6",
        "account": "smartx",
        "folder_kind": "inbox",
        "from_addr": "jongwon@smartx.kr",
        "subject": "Re: [격주보고서] 개인 진행 현황 보고 (26.03.27, 이종범)",
    }

    result = classify_message(message, sender_map)
    labels = {entry["label"]: entry for entry in result["labels"]}

    assert "advisor-fyi" in labels
    assert "advisor-request" not in labels


def test_classify_message_does_not_treat_static_as_ta_keyword():
    sender_map = {}
    message = {
        "message_id": "m3",
        "account": "personal",
        "folder_kind": "inbox",
        "from_addr": "noreply@example.org",
        "subject": "HERMES TEST GIST-FORWARD STATIC-001",
    }

    result = classify_message(message, sender_map)
    labels = {entry["label"] for entry in result["labels"]}

    assert "ta" not in labels
