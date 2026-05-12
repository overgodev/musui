"""Generate a Thai reply via orchestrator (3.11) and convert to akane voice (akanev2.pth) using rvc-python (3.10)."""

import asyncio
import pathlib
import sys

import edge_tts
import requests
import torch.serialization
from fairseq.data.dictionary import Dictionary
from rvc_python.infer import RVCInference


ORCH_URL = "http://localhost:8002/decide"
MODEL_PATH = pathlib.Path("voice model/akane/akanev2.pth")
INDEX_PATH = pathlib.Path("voice model/akane/added_IVF158_Flat_nprobe_1_akanev2_v2.index")
SRC_WAV = pathlib.Path("artifacts/audio/src_edge.wav")
OUT_WAV = pathlib.Path("artifacts/audio/akane_out.wav")


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", "ignore"))


def fetch_reply() -> str:
    payload = {
        "author": {"author_id": "u1", "display_name": "ปลาเผา"},
        "text": "วันนี้เล่นเกมอะไร",
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


def run_rvc() -> None:
    torch.serialization.add_safe_globals([Dictionary])
    OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
    rvc = RVCInference(
        model_path=str(MODEL_PATH),
        index_path=str(INDEX_PATH),
        device="cpu:0",
        version="v2",
    )
    rvc.set_params(index_rate=0.75, protect=0.33, f0method="pm")
    rvc.infer_file(str(SRC_WAV), str(OUT_WAV))


def main() -> None:
    reply = fetch_reply()
    safe_print(f"Reply: {reply}")
    asyncio.run(synth_edge(reply))
    run_rvc()
    safe_print(f"Audio: {OUT_WAV.resolve()}")


if __name__ == "__main__":
    main()
