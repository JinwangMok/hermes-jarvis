from pathlib import Path

from runtime.helpers import output_text_path, transcription_endpoint


def test_transcription_endpoint_appends_openai_path_once():
    assert transcription_endpoint("http://127.0.0.1:8177") == "http://127.0.0.1:8177/v1/audio/transcriptions"
    assert transcription_endpoint("http://127.0.0.1:8177/") == "http://127.0.0.1:8177/v1/audio/transcriptions"
    assert transcription_endpoint("http://127.0.0.1:8177/v1/audio/transcriptions") == "http://127.0.0.1:8177/v1/audio/transcriptions"


def test_output_text_path_uses_input_stem_inside_output_dir(tmp_path: Path):
    input_path = tmp_path / "utterance.sample.wav"
    input_path.write_bytes(b"wav")

    out = output_text_path(tmp_path / "out", input_path)

    assert out == tmp_path / "out" / "utterance.sample.txt"
