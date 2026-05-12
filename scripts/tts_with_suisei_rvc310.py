"""Generate a Thai reply via orchestrator (3.11) and convert to suisei voice using rvc-python (3.10)."""

import argparse
import asyncio
import pathlib
import random
import sys

import edge_tts
import requests
import torch.serialization
from fairseq.data.dictionary import Dictionary
from rvc_python.infer import RVCInference


ORCH_URL = "http://localhost:8002/decide"
MODEL_PATH = pathlib.Path("voice model/suisei/SuiseiFT.pth")
INDEX_PATH = pathlib.Path("voice model/suisei/added_IVF471_Flat_nprobe_1_SuiseiFT_v2.index")
SRC_WAV = pathlib.Path("artifacts/audio/src_edge.wav")
OUT_WAV = pathlib.Path("artifacts/audio/suisei_out.wav")
MOODS = {
    "calm": {"f0method": "rmvpe", "f0up_key": 0, "index_rate": 0.7, "protect": 0.33},
    "bright": {"f0method": "rmvpe", "f0up_key": 2, "index_rate": 0.8, "protect": 0.2},
    "soft": {"f0method": "rmvpe", "f0up_key": -1, "index_rate": 0.72, "protect": 0.38},
    "teasing": {"f0method": "rmvpe", "f0up_key": 1, "index_rate": 0.78, "protect": 0.25},
}


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", "ignore"))


def fetch_reply(override_text: str | None = None) -> str:
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


async def synth_edge(text: str) -> None:
    SRC_WAV.parent.mkdir(parents=True, exist_ok=True)
    await edge_tts.Communicate(text=text, voice="th-TH-PremwadeeNeural").save(str(SRC_WAV))


def run_rvc(mood: str) -> None:
    torch.serialization.add_safe_globals([Dictionary])
    OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
    preset = MOODS.get(mood, MOODS["calm"])
    rvc = RVCInference(
        model_path=str(MODEL_PATH),
        index_path=str(INDEX_PATH),
        device="cpu:0",
        version="v2",
    )
    rvc.set_params(
        index_rate=preset["index_rate"],
        protect=preset["protect"],
        f0method=preset["f0method"],
        f0up_key=preset["f0up_key"],
    )
    rvc.infer_file(str(SRC_WAV), str(OUT_WAV))


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM -> suisei RVC")
    parser.add_argument(
        "--text",
        action="append",
        help="Override reply text. Can be repeated; if multiple, a random one is chosen.",
    )
    parser.add_argument("--mood", default="calm", choices=list(MOODS.keys()))
    parser.add_argument(
        "--sample-stream",
        action="store_true",
        help="Use built-in streamy Thai sentence pool and pick one at random.",
    )
    args = parser.parse_args()

    stream_pool = [
        "คืนนี้ถ้าชนะบอส ฉันจะเปิดคาราโอเกะเฉพาะกิจให้แชต",
        "ห้ามสปอยล์เนื้อเรื่องนะ อยากลุ้นเอง",
        "มุกปิงหน่วงใช้ได้แค่สามครั้งต่อสตรีม จำไว้",
        "ขอทำนายดวง บอสจะลงโทษเราหรือไม่",
        "ถ้าตกเหวอีกครั้ง จะให้บอทตัดคลิปแฉตัวเอง",
        "แชตเร็วมาก ขอสลับโหมดสุ่มตอบนะ",
        "เสียงเอฟเฟกต์เมื่อกี้ใครได้ยินบ้าง หลอนสุดๆ",
        "พลังงานเริ่มตก ขอจิบน้ำแล้วลุยต่อ",
        "มีใครมีคำคมกำลังใจสั้นๆ ให้ทีมงานในหัวบ้าง",
        "ถ้าเกมค้าง จะเปลี่ยนไปเกมดนตรีทันที เตือนแล้วนะ",
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
    asyncio.run(synth_edge(reply))
    run_rvc(args.mood)
    safe_print(f"Audio: {OUT_WAV.resolve()}")


if __name__ == "__main__":
    main()
