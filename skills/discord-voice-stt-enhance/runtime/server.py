#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

ALLOWED_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.webm', '.mp4'}
MAX_FILE_SIZE = 25 * 1024 * 1024
DEFAULT_MODEL = os.environ.get('HERMES_LOCAL_STT_MODEL', 'large-v3-turbo')
DEFAULT_HOST = os.environ.get('HERMES_LOCAL_STT_HOST', '127.0.0.1')
DEFAULT_PORT = int(os.environ.get('HERMES_LOCAL_STT_PORT', '8177'))
DEFAULT_DOWNLOAD_ROOT = os.environ.get(
    'HERMES_LOCAL_STT_CACHE_DIR',
    str(Path(__file__).resolve().parent / '.cache' / 'models'),
)
DEFAULT_DEVICE = os.environ.get('HERMES_LOCAL_STT_DEVICE', 'cuda')
DEFAULT_COMPUTE_TYPE = os.environ.get('HERMES_LOCAL_STT_COMPUTE_TYPE', 'int8_float16')
DEFAULT_CPU_COMPUTE_TYPE = os.environ.get('HERMES_LOCAL_STT_CPU_COMPUTE_TYPE', 'int8')
DEFAULT_BEAM_SIZE = int(os.environ.get('HERMES_LOCAL_STT_BEAM_SIZE', '5'))

logging.basicConfig(
    level=os.environ.get('HERMES_LOCAL_STT_LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger('hermes-local-stt')

_model = None
_model_name = None
_model_lock = threading.Lock()


def _load_model(model_name: str):
    global _model, _model_name
    if _model is not None and _model_name == model_name:
        return _model

    with _model_lock:
        if _model is not None and _model_name == model_name:
            return _model

        from faster_whisper import WhisperModel

        attempts: list[tuple[str, str]] = []
        preferred_device = DEFAULT_DEVICE.strip().lower() or 'cuda'
        preferred_compute = DEFAULT_COMPUTE_TYPE.strip() or 'int8_float16'
        cpu_compute = DEFAULT_CPU_COMPUTE_TYPE.strip() or 'int8'

        if preferred_device == 'cpu':
            attempts.append(('cpu', cpu_compute))
        elif preferred_device == 'auto':
            attempts.extend([('cuda', preferred_compute), ('cpu', cpu_compute)])
        else:
            attempts.extend([(preferred_device, preferred_compute), ('cpu', cpu_compute)])

        last_error = None
        for device, compute_type in attempts:
            try:
                logger.info(
                    'Loading faster-whisper model %s (device=%s compute=%s cache=%s)',
                    model_name,
                    device,
                    compute_type,
                    DEFAULT_DOWNLOAD_ROOT,
                )
                _model = WhisperModel(
                    model_name,
                    device=device,
                    compute_type=compute_type,
                    download_root=DEFAULT_DOWNLOAD_ROOT,
                )
                _model_name = model_name
                logger.info('Loaded model %s on %s', model_name, device)
                return _model
            except Exception as exc:  # pragma: no cover - fallback path exercised in runtime
                last_error = exc
                logger.warning('Failed to load model %s on %s: %s', model_name, device, exc)

        raise RuntimeError(f'Failed to load model {model_name}: {last_error}')


def get_model(model_name: str | None = None):
    return _load_model(model_name or DEFAULT_MODEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get('HERMES_LOCAL_STT_PRELOAD', '1') not in {'0', 'false', 'False'}:
        get_model(DEFAULT_MODEL)
    yield


app = FastAPI(title='Hermes Local STT Runtime', lifespan=lifespan)


@app.get('/health')
async def health() -> dict[str, Any]:
    return {
        'status': 'ok' if _model is not None else 'loading',
        'model': _model_name or DEFAULT_MODEL,
        'host': DEFAULT_HOST,
        'port': DEFAULT_PORT,
    }


@app.post('/v1/audio/transcriptions')
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default=DEFAULT_MODEL),
    language: str | None = Form(default=None),
    response_format: str = Form(default='json'),
    temperature: float = Form(default=0.0),
):
    model_instance = get_model(model)
    raw_suffix = Path(file.filename or 'audio.wav').suffix.lower()
    suffix = raw_suffix if raw_suffix in ALLOWED_EXTENSIONS else '.wav'
    payload = await file.read()
    if len(payload) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail='File too large. Maximum 25MB.')

    with tempfile.NamedTemporaryFile(prefix='hermes-local-stt-', suffix=suffix, delete=False) as tmp:
        tmp.write(payload)
        tmp_path = tmp.name

    kwargs: dict[str, Any] = {'beam_size': DEFAULT_BEAM_SIZE, 'temperature': temperature}
    if language:
        kwargs['language'] = language

    start = time.time()
    try:
        segments, info = model_instance.transcribe(tmp_path, **kwargs)
        text = ' '.join(segment.text.strip() for segment in segments).strip()
        elapsed = round(time.time() - start, 2)
        logger.info(
            'Transcribed %s via %s (lang=%s prob=%.2f duration=%.2fs elapsed=%.2fs)',
            Path(file.filename or tmp_path).name,
            model,
            getattr(info, 'language', ''),
            float(getattr(info, 'language_probability', 0.0) or 0.0),
            float(getattr(info, 'duration', 0.0) or 0.0),
            elapsed,
        )
        if response_format == 'text':
            return PlainTextResponse(text)
        return {
            'text': text,
            'language': getattr(info, 'language', None),
            'language_probability': getattr(info, 'language_probability', None),
            'duration': getattr(info, 'duration', None),
            'processing_time': elapsed,
            'model': model,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error('Transcription failed: %s', exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f'Transcription failed: {exc}')
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description='Run the Hermes local faster-whisper STT server.')
    parser.add_argument('--host', default=DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--reload', action='store_true')
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload, log_level='info')


if __name__ == '__main__':
    main()
