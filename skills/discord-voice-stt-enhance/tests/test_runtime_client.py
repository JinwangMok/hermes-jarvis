from runtime.client import filter_transcript_hallucination


def test_filter_transcript_hallucination_drops_korean_youtube_closers():
    assert filter_transcript_hallucination("시청해주셔서 감사합니다.") == ""
    assert filter_transcript_hallucination("시청해 주셔서 감사합니다") == ""
    assert filter_transcript_hallucination("감사합니다.") == ""


def test_filter_transcript_hallucination_preserves_real_content_with_polite_word():
    assert filter_transcript_hallucination("필터 추가해 줘서 감사합니다") == "필터 추가해 줘서 감사합니다"
    assert filter_transcript_hallucination("감사합니다 다음 작업 계속 진행") == "감사합니다 다음 작업 계속 진행"


def test_filter_transcript_hallucination_drops_common_english_youtube_closer():
    assert filter_transcript_hallucination("Thank you for watching.") == ""


def test_filter_transcript_hallucination_drops_repeated_filler_syllables():
    assert filter_transcript_hallucination("아, 아, 아, 아, 아, 아, 아, 아, 아, 아") == ""
    assert filter_transcript_hallucination("어 어 어 어 어 어 어") == ""
    assert filter_transcript_hallucination("음... 음... 음... 음... 음...") == ""


def test_filter_transcript_hallucination_preserves_short_meaningful_filler_context():
    assert filter_transcript_hallucination("아 지금 들려?") == "아 지금 들려?"
