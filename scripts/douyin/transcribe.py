"""视频/音频 ASR：优先 SenseVoice（funasr），不可用时 fallback faster-whisper。"""
from __future__ import annotations

from typing import Any

_MODEL: Any = None
_WHISPER: Any = None


def _load_funasr():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    from funasr import AutoModel

    _MODEL = AutoModel(
        model="iic/SenseVoiceSmall",
        trust_remote_code=True,
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",
    )
    return _MODEL


def _transcribe_funasr(audio_path: str) -> str:
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    model = _load_funasr()
    result = model.generate(
        input=audio_path,
        language="zh",
        use_itn=True,
        batch_size_s=60,
    )
    parts: list[str] = []
    if result:
        for row in result:
            if isinstance(row, dict) and row.get("text"):
                parts.append(rich_transcription_postprocess(row["text"]))
    return "\n\n".join(p for p in parts if p.strip())


def _load_whisper():
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel

        _WHISPER = WhisperModel("small", device="cpu", compute_type="int8")
    return _WHISPER


def _transcribe_whisper(audio_path: str) -> str:
    model = _load_whisper()
    segments, _ = model.transcribe(audio_path, language="zh")
    return "\n\n".join(s.text.strip() for s in segments if s.text.strip())


def transcribe_audio(audio_path: str) -> tuple[str, str]:
    """返回 (text, transcriber_label)。"""
    try:
        return _transcribe_funasr(audio_path), "SenseVoice-Small"
    except Exception:
        pass
    try:
        return _transcribe_whisper(audio_path), "faster-whisper-small"
    except Exception as e:
        raise RuntimeError(
            "ASR 失败。请安装 funasr（Python≤3.12）或 faster-whisper："
            "pip install -r requirements-douyin.txt"
        ) from e
