"""Generate a Thai reply via orchestrator (3.11) and convert to mosuiV2 voice using rvc-python (3.10)."""

import argparse
import asyncio
import pathlib
import random
import sys
from typing import Optional

import edge_tts
import requests
import torch
from fairseq.data.dictionary import Dictionary
from rvc_python.infer import RVCInference


ORCH_URL = "http://localhost:8002/decide"
MODEL_PATH = pathlib.Path("voice model/mosuiV2/mosui_v2.pth")
INDEX_PATH = pathlib.Path("voice model/mosuiV2/mosui_v2.index")
SRC_WAV = pathlib.Path("artifacts/audio/src_edge.wav")
OUT_WAV = pathlib.Path("artifacts/audio/mosui_v2_out.wav")

MOODS = {
    # Match chaaym baseline: harvest for stability, moderate protect/rms.
    "natural": {"f0method": "harvest", "f0up_key": 0, "index_rate": 0.9, "protect": 0.28, "rms_mix_rate": 0.9},
    "bright": {"f0method": "harvest", "f0up_key": 2, "index_rate": 0.9, "protect": 0.25, "rms_mix_rate": 0.95},
    "soft": {"f0method": "harvest", "f0up_key": -1, "index_rate": 0.88, "protect": 0.3, "rms_mix_rate": 0.9},
    "teasing": {"f0method": "harvest", "f0up_key": 1, "index_rate": 0.9, "protect": 0.25, "rms_mix_rate": 0.95},
    "soft_v2": {"f0method": "harvest", "f0up_key": -2, "index_rate": 0.86, "protect": 0.32, "rms_mix_rate": 0.9},
    "cool": {"f0method": "harvest", "f0up_key": 1, "index_rate": 0.92, "protect": 0.26, "rms_mix_rate": 0.95},
}


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", "ignore"))


def fetch_reply(override_text: Optional[str] = None) -> str:
    payload = {
        "author": {"author_id": "u1", "display_name": "ปลาเผา"},
        "text": override_text or "วันนี้เล่นเกมอะไร",
        "source": "youtube",
    }
    try:
        resp = requests.post(ORCH_URL, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json().get("reply_text_th") or payload["text"]
    except Exception:
        return payload["text"]


def has_thai(text: str) -> bool:
    return any("\u0e00" <= ch <= "\u0e7f" for ch in text)


def has_english(text: str) -> bool:
    return any("a" <= ch.lower() <= "z" for ch in text)


async def synth_edge(text: str, rate: str, pitch: str, volume: str) -> None:
    SRC_WAV.parent.mkdir(parents=True, exist_ok=True)
    english_only = has_english(text) and not has_thai(text)
    if english_only:
        voice = "en-US-JennyNeural"
        use_rate = "-4%"
        pitch_local = pitch
    else:
        voice = "th-TH-PremwadeeNeural"
        has_mix_en = has_english(text)
        use_rate = rate
        pitch_local = pitch
    await edge_tts.Communicate(text=text, voice=voice, rate=use_rate, pitch=pitch_local, volume=volume).save(str(SRC_WAV))


def run_rvc(
    mood: str,
    index_rate_override: float | None,
    protect_override: float | None,
    rms_mix_override: float | None,
    disable_index: bool,
) -> None:
    if hasattr(torch.serialization, "add_safe_globals"):
        torch.serialization.add_safe_globals([Dictionary])
    OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
    preset = MOODS.get(mood, MOODS["natural"])
    index_path = str(INDEX_PATH) if INDEX_PATH.exists() and not disable_index else ""
    rvc = RVCInference(
        device="cpu:0",
        version="v2",
    )
    # Force full precision to avoid half-related artifacts on CPU
    if hasattr(rvc, "config") and hasattr(rvc.config, "is_half"):
        rvc.config.is_half = False
    if hasattr(rvc, "vc") and hasattr(rvc.vc, "is_half"):
        rvc.vc.is_half = False
    rvc.load_model(str(MODEL_PATH), version="v2", index_path=index_path)
    rvc.set_params(
        index_rate=(index_rate_override if index_rate_override is not None else preset["index_rate"]) if index_path else 0.0,
        protect=protect_override if protect_override is not None else preset["protect"],
        rms_mix_rate=rms_mix_override if rms_mix_override is not None else preset.get("rms_mix_rate", 1.0),
        f0method=preset["f0method"],
        f0up_key=preset["f0up_key"],
    )
    rvc.infer_file(str(SRC_WAV), str(OUT_WAV))
    fade_out = 70 if mood == "soft_v2" else 50
    trim_wav(OUT_WAV, head_ms=40, tail_ms=50, fade_out_ms=fade_out)


def trim_wav(path: pathlib.Path, head_ms: int, tail_ms: int, fade_out_ms: int = 80, silence_db: float = -30.0, pad_ms: int = 30, max_len_s: float = 6.0) -> None:
    import soundfile as sf
    import numpy as np
    data, sr = sf.read(path)
    # Trim leading/trailing silence based on threshold
    if data.ndim == 1:
        mags = np.abs(data)
    else:
        mags = np.max(np.abs(data), axis=1)
    thresh = 10 ** (silence_db / 20)
    active = np.where(mags > thresh)[0]
    if active.size > 0:
        pad = int(sr * pad_ms / 1000)
        start = max(active[0] - pad, 0)
        end = min(active[-1] + pad, len(data) - 1)
        data = data[start : end + 1]
    start = int(sr * head_ms / 1000)
    end = len(data) - int(sr * tail_ms / 1000)
    if end <= start:
        return
    segment = data[start:end]
    # Enforce max length
    max_samples = int(max_len_s * sr)
    if len(segment) > max_samples:
        segment = segment[:max_samples]
    fade_len = min(len(segment), int(sr * fade_out_ms / 1000))
    if fade_len > 0:
        fade = np.linspace(1.0, 0.0, fade_len, dtype=segment.dtype)
        if segment.ndim > 1:
            segment[-fade_len:, :] = segment[-fade_len:, :] * fade[:, None]
        else:
            segment[-fade_len:] = segment[-fade_len:] * fade
    sf.write(path, segment, sr)


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM -> mosuiV2 RVC")
    parser.add_argument(
        "--text",
        action="append",
        help="Override reply text. Can be repeated; if multiple, a random one is chosen.",
    )
    parser.add_argument("--mood", default="natural", choices=list(MOODS.keys()))
    parser.add_argument(
        "--sample-stream",
        action="store_true",
        help="Use built-in streamy Thai sentence pool and pick one at random.",
    )
    parser.add_argument("--index-rate", type=float, help="Override index mix (0-1).")
    parser.add_argument("--protect", type=float, help="Override protect (0-1).")
    parser.add_argument("--rms-mix", type=float, help="Override rms_mix_rate (0-1).")
    parser.add_argument("--no-index", action="store_true", help="Disable feature index use.")
    parser.add_argument("--rate", default="+1%", help="Edge TTS rate (e.g., +3% or -2%).")
    parser.add_argument("--pitch", default="+20Hz", help="Edge TTS pitch (must be like +60Hz or -50Hz).")
    parser.add_argument("--volume", default="+2%", help="Edge TTS volume (e.g., +6% or -2%).")
    args = parser.parse_args()

    stream_pool = [
        "ดรอปของดีแล้ว อย่าเพิ่งตาย แชตรอดูก่อนนะ",
        "เซิร์ฟแม่งแลค โทษปิงได้มั้ย 555",
        "มีใครเห็นบอสเมื่อกี้บินไหม หรือฉันตาฝาด",
        "ขอพักดื่มน้ำแป๊บ โมเดเรเตอร์ฝากดูแชตด้วย",
        "ถ้าเกมค้างอีก ฉันจะเปลี่ยนไปเกมเต้นแล้วนะ",
        "แชตเร็วมาก ขอสลับโหมดสุ่มตอบนะ",
        "เสียงเอฟเฟกต์เมื่อกี้หลอนใครไหม หรือแค่ฉัน",
        "โหวตหน่อย จะไปดันแรงค์หรือทำเควสโง่ๆ ต่อ",
        "คืนนี้ถ้าเกมไม่พังก็ถือว่าปาฏิหาริย์",
        "เอฟเฟกต์ชนะบอสต้องดังหน่อย เตรียมหูไว้",
    ]

    if args.sample_stream:
        chosen_text = random.choice(stream_pool)
    elif args.text and len(args.text) > 0:
        chosen_text = random.choice(args.text)
    else:
        chosen_text = None

    reply = fetch_reply(chosen_text)
    safe_print(f"Reply: {reply}")
    safe_print(f"Mood: {args.mood}")
    asyncio.run(synth_edge(reply, args.rate, args.pitch, args.volume))
    run_rvc(args.mood, args.index_rate, args.protect, args.rms_mix, args.no_index)
    safe_print(f"Audio: {OUT_WAV.resolve()}")


if __name__ == "__main__":
    main()
