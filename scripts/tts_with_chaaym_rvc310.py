"""Generate a Thai reply via orchestrator (3.11) and convert to chaaym voice using rvc-python (3.10).
best test setting 
.\.venv310_rvc\Scripts\python scripts/tts_with_chaaym_rvc310.py ^
  --text "ขอเสียงเชียร์หน่อย จะไปเกมต่อหรือพัก break ดี" ^
  --mood natural --no-index --protect 0.28 --rms-mix 0.95 ^
  --rate +3% --pitch +60Hz --volume +6%

"""

import argparse
import asyncio
import pathlib
import random
import sys
from typing import Optional

import edge_tts
import requests
import torch.serialization
from fairseq.data.dictionary import Dictionary
from rvc_python.infer import RVCInference


ORCH_URL = "http://localhost:8002/decide"
MODEL_PATH = pathlib.Path("voice model/chaaym/chaaym_v1.pth")
INDEX_PATH = pathlib.Path("voice model/chaaym/chaaym_v1.index")
SRC_WAV = pathlib.Path("artifacts/audio/src_edge.wav")
OUT_WAV = pathlib.Path("artifacts/audio/chaaym_out.wav")

MOODS = {
    # Favor harvest + higher protect to reduce robotic artifacts
    "natural": {"f0method": "harvest", "f0up_key": 0, "index_rate": 0.9, "protect": 0.28, "rms_mix_rate": 0.9},
    "bright": {"f0method": "harvest", "f0up_key": 2, "index_rate": 0.9, "protect": 0.25, "rms_mix_rate": 0.95},
    "soft": {"f0method": "harvest", "f0up_key": -1, "index_rate": 0.88, "protect": 0.3, "rms_mix_rate": 0.9},
    "teasing": {"f0method": "harvest", "f0up_key": 1, "index_rate": 0.9, "protect": 0.25, "rms_mix_rate": 0.95},
    # Softer, warmer variant requested as v2
    "soft_v2": {"f0method": "harvest", "f0up_key": -2, "index_rate": 0.86, "protect": 0.32, "rms_mix_rate": 0.88},
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


def wrap_english(text: str) -> str:
    def mark(tok: str) -> str:
        is_en = has_english(tok) and not has_thai(tok)
        return f'<lang xml:lang="en-US">{tok}</lang>' if is_en else tok
    return " ".join(mark(t) for t in text.split())


async def synth_edge(text: str, rate: str, pitch: str, volume: str, keep_english: bool, mood: str) -> None:
    SRC_WAV.parent.mkdir(parents=True, exist_ok=True)
    english_only = has_english(text) and not has_thai(text)
    pitch_local = pitch

    if english_only:
        payload = text  # straight English
        voice = "en-US-JennyNeural"
        use_rate = "-4%"  # slow a bit for clarity
        pitch_local = pitch  # keep same pitch contour as Thai for consistency
    else:
        # Mixed Thai/English: keep single Thai voice; mild slow and slight pitch lift for mix
        voice = "th-TH-PremwadeeNeural"
        base_text = text.replace("สั้นๆ", "สั้นๆ,")
        has_mix_en = has_english(text)
        use_rate = "-2%" if has_mix_en else rate
        pitch_local = pitch  # keep pitch consistent across Thai/English
        payload = base_text

    await edge_tts.Communicate(text=payload, voice=voice, rate=use_rate, pitch=pitch_local, volume=volume).save(str(SRC_WAV))


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
    rvc = RVCInference(device="cpu:0", version="v2")
    # Force full precision before loading model
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
    trim_wav(OUT_WAV, head_ms=240, tail_ms=300)


def trim_wav(path: pathlib.Path, head_ms: int, tail_ms: int) -> None:
    import soundfile as sf
    data, sr = sf.read(path)
    start = int(sr * head_ms / 1000)
    end = len(data) - int(sr * tail_ms / 1000)
    if end <= start:
        return
    sf.write(path, data[start:end], sr)


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM -> chaaym RVC")
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
    parser.add_argument("--rate", default="+3%", help="Edge TTS rate (e.g., +3% or -2%).")
    parser.add_argument("--pitch", default="+60Hz", help="Edge TTS pitch (must be like +60Hz or -50Hz).")
    parser.add_argument("--volume", default="+6%", help="Edge TTS volume (e.g., +6% or -2%).")
    parser.add_argument("--keep-english", action="store_true", help="Wrap English tokens with en-US lang to keep straight English pronunciation.")
    args = parser.parse_args()

    stream_pool = [
        "พร้อมยัง แชตจะให้สุ่มตอบแล้วนะ",
        "เจอบอสลับอีกตัว เดี๋ยวขอปิงปองก่อน",
        "คืนนี้มุกอาจหมดเร็ว ฝากเติมด้วย",
        "ขอเบรคจิบชา แล้วไปต่อแรงค์",
        "ใครได้ยินเอฟเฟกต์วิบวับเมื่อกี้ไหม หรือแค่ฉัน",
        "ถ้าบอสบินอีกครั้ง จะโทษปิงทันที",
        "เสียงเกมดังกว่าเสียงฉันไหม ปรับบอกได้นะ",
        "แชตเร็วแบบนี้ ขอสุ่มหยิบข้อความนะ",
        "โหวตสั้นๆ เล่นต่อหรือไปเกมดนตรี",
        "อย่าเพิ่งสปอยล์ ขอเล่นเองให้จบก่อน",
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
    asyncio.run(synth_edge(reply, args.rate, args.pitch, args.volume, args.keep_english, args.mood))
    run_rvc(args.mood, args.index_rate, args.protect, args.rms_mix, args.no_index)
    safe_print(f"Audio: {OUT_WAV.resolve()}")


if __name__ == "__main__":
    main()
