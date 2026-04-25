from pathlib import Path
from urllib.parse import urlparse


def transcription_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1/audio/transcriptions"):
        return normalized
    parsed = urlparse(normalized)
    if parsed.scheme and parsed.netloc:
        return f"{normalized}/v1/audio/transcriptions"
    raise ValueError(f"Invalid base URL: {base_url}")


def output_text_path(output_dir: str | Path, input_path: str | Path) -> Path:
    out_dir = Path(output_dir)
    in_path = Path(input_path)
    return out_dir / f"{in_path.stem}.txt"
