"""Generate a Thai reply via orchestrator (on 3.11) and convert to mosui voice with rvc-python (on 3.10)."""

import argparse
import asyncio
import pathlib
import random
import sys
from typing import Optional, Sequence

import edge_tts
import requests

import torch.serialization
from fairseq.data.dictionary import Dictionary
from rvc_python.infer import RVCInference


ORCH_URL = "http://localhost:8002/decide"
MODEL_PATH = pathlib.Path("voice model/mosui/mosui.pth")
INDEX_PATH = pathlib.Path("voice model/mosui/mosui.index")
SRC_WAV = pathlib.Path("artifacts/audio/src_edge.wav")
OUT_WAV = pathlib.Path("artifacts/audio/mosui_out.wav")
MOODS = {
    # use rmvpe for stable f0 extraction; adjust pitch and index mix for flavor
    "calm": {"f0method": "rmvpe", "f0up_key": 0, "index_rate": 0.7, "protect": 0.33},
    "bright": {"f0method": "rmvpe", "f0up_key": 2, "index_rate": 0.8, "protect": 0.2},
    "soft": {"f0method": "rmvpe", "f0up_key": -1, "index_rate": 0.72, "protect": 0.38},
    "teasing": {"f0method": "rmvpe", "f0up_key": 1, "index_rate": 0.78, "protect": 0.25},
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


async def synth_edge(text: str) -> None:
    SRC_WAV.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text=text, voice="th-TH-PremwadeeNeural")
    await communicate.save(str(SRC_WAV))


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
    parser = argparse.ArgumentParser(description="LLM -> mosui RVC")
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

    stream_pool: Sequence[str] = [
        "ดรอปของดีแล้ว อย่าเพิ่งตาย แชตรอดูก่อนนะ",
        "เซิร์ฟแม่งแลค โทษปิงได้มั้ย 555",
        "มีใครเห็นบอสเมื่อกี้บินไหม หรือฉันตาฝาด",
        "ขอพักดื่มน้ำแป๊บ โมเดเรเตอร์ฝากดูแชตด้วย",
        "ถ้าเกมค้างอีก ฉันจะเปลี่ยนไปเกมเต้นแล้วนะ",
        "ขอบคุณโดเนตนะ เดี๋ยวฉันจะใช้ซื้อน้ำปลา",
        "ใครเล่นปั่นมุกเดิม ขอตัดแต้มความเชื่อถือหนึ่งครั้ง",
        "โหวตหน่อย จะไปดันแรงค์หรือทำเควสโง่ๆ ต่อ",
        "แชตเร็วขนาดนี้ ฉันจะสุ่มตอบแล้วนะ",
        "ห้ามสปอยล์เนื้อเรื่อง ถ้าสปอยล์จะให้บอทอ่านอเวนเจอร์สภาคแรกใส่เลย",
        "เอฟเฟกต์เสียงเมื่อกี้หลอนใครไหม หรือแค่ฉัน",
        "มีใครมีมุกตีบอสมังกรไหม ฉันเริ่มหมดคลังแล้ว",
        "ถ้าใครเห็นฉันตกเหวเมื่อกี้ ช่วยแกล้งทำเป็นไม่เห็น",
        "คืนนี้ถ้าเกมไม่พังก็ถือว่าปาฏิหาริย์",
        "อยากได้คำทายลูกแก้ว วันนี้ดวงจะดีไหม",
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
