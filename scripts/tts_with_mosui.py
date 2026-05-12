"""Generate a reply with the orchestrator and voice-convert it to mosui (RVC)."""

import asyncio
import pathlib
import subprocess
import sys
from typing import Optional

import requests
import edge_tts

ORCHESTRATOR_URL = "http://localhost:8002/decide"
MODEL_PATH = pathlib.Path("voice model/mosui/mosui.pth")
INDEX_PATH = pathlib.Path("voice model/mosui/mosui.index")
SRC_WAV = pathlib.Path("artifacts/audio/src_edge.wav")
OUT_WAV = pathlib.Path("artifacts/audio/mosui_out.wav")


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", "ignore"))


def fetch_reply(text: str) -> Optional[str]:
    payload = {
        "author": {"author_id": "u1", "display_name": "ปลาเผา"},
        "text": text,
        "source": "youtube",
    }
    try:
        resp = requests.post(ORCHESTRATOR_URL, json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json().get("reply_text_th")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] orchestrator not reachable, using base text. {exc}")
        return None


async def synth_edge(text: str, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text=text, voice="th-TH-PremwadeeNeural")
    await communicate.save(str(path))


def run_rvc(src: pathlib.Path, dst: pathlib.Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "rvc_python",
        "cli",
        "-i",
        str(src),
        "-o",
        str(dst),
        "-mp",
        str(MODEL_PATH),
        "-de",
        "cpu",
        "-ip",
        str(INDEX_PATH),
        "-f0m",
        "pm",
        "-ir",
        "0.75",
        "-pro",
        "0.33",
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    base_text = "วันนี้เล่นเกมอะไร"
    reply = fetch_reply(base_text) or base_text
    safe_print(f"Reply text: {reply}")

    asyncio.run(synth_edge(reply, SRC_WAV))
    run_rvc(SRC_WAV, OUT_WAV)
    safe_print(f"Audio saved: {OUT_WAV.resolve()}")


if __name__ == "__main__":
    main()
