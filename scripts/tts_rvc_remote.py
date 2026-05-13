"""Generate Thai TTS with edge-tts then convert with remote RVC WebUI.

Usage:
  python scripts/tts_rvc_remote.py --text "สวัสดีครับ" --pitch 0
  python scripts/tts_rvc_remote.py --sample-stream
  python scripts/tts_rvc_remote.py --text "ข้อความ" --rvc-url http://192.168.1.17:7865
"""

import argparse
import asyncio
import pathlib
import random
import sys

import edge_tts
import httpx


RVC_URL = "http://192.168.1.17:7865"
VOICE = "th-TH-PremwadeeNeural"
SRC_WAV = pathlib.Path("artifacts/audio/src_edge_remote.wav")
OUT_WAV = pathlib.Path("artifacts/audio/rvc_remote_out.wav")

STREAM_POOL = [
    "ดรอปของดีแล้ว อย่าเพิ่งตาย แชตรอดูก่อนนะ",
    "เซิร์ฟแม่งแลค โทษปิงได้มั้ย 555",
    "มีใครเห็นบอสเมื่อกี้บินไหม หรือฉันตาฝาด",
    "ขอพักดื่มน้ำแป๊บ โมเดเรเตอร์ฝากดูแชตด้วย",
    "ถ้าเกมค้างอีก ฉันจะเปลี่ยนไปเกมเต้นแล้วนะ",
    "ขอบคุณโดเนตนะ เดี๋ยวฉันจะใช้ซื้อน้ำปลา",
    "โหวตหน่อย จะไปดันแรงค์หรือทำเควสโง่ๆ ต่อ",
    "แชตเร็วขนาดนี้ ฉันจะสุ่มตอบแล้วนะ",
    "คืนนี้ถ้าเกมไม่พังก็ถือว่าปาฏิหาริย์",
]


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", "ignore"))


async def synth_edge(text: str) -> None:
    SRC_WAV.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text=text, voice=VOICE)
    await communicate.save(str(SRC_WAV))


async def rvc_convert(rvc_url: str, pitch: int) -> None:
    wav_bytes = SRC_WAV.read_bytes()

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Upload audio to Gradio server
        upload_resp = await client.post(
            f"{rvc_url}/upload",
            files={"files": ("input.wav", wav_bytes, "audio/wav")},
        )
        upload_resp.raise_for_status()
        upload_data = upload_resp.json()

        first = upload_data[0]
        uploaded_path = first if isinstance(first, str) else (first.get("path") or first.get("name"))
        safe_print(f"Uploaded: {uploaded_path}")

        # Run voice conversion
        infer_resp = await client.post(
            f"{rvc_url}/run/infer_convert",
            json={
                "data": [0, uploaded_path, pitch, "rmvpe", "", "", 0.75, 3, 0, 0.25, 0.33]
            },
        )
        infer_resp.raise_for_status()
        result_data = infer_resp.json().get("data", [])

        audio_output = result_data[1] if len(result_data) >= 2 else None
        if audio_output is None:
            raise RuntimeError(f"No audio in response: {result_data}")

        if isinstance(audio_output, str):
            audio_file_path = audio_output
        elif isinstance(audio_output, dict):
            audio_file_path = audio_output.get("path") or audio_output.get("name")
        else:
            raise RuntimeError(f"Unknown audio output format: {audio_output}")

        # Download the converted file
        audio_resp = await client.get(f"{rvc_url}/file={audio_file_path}")
        audio_resp.raise_for_status()
        OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
        OUT_WAV.write_bytes(audio_resp.content)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Thai TTS → Remote RVC voice conversion")
    parser.add_argument("--text", help="Thai text to synthesize")
    parser.add_argument("--pitch", type=int, default=0, help="Pitch shift in semitones (default 0)")
    parser.add_argument("--rvc-url", default=RVC_URL, help=f"RVC WebUI URL (default: {RVC_URL})")
    parser.add_argument("--sample-stream", action="store_true", help="Use random sample Thai text")
    args = parser.parse_args()

    if args.sample_stream:
        text = random.choice(STREAM_POOL)
    elif args.text:
        text = args.text
    else:
        parser.print_help()
        return

    safe_print(f"Text: {text}")
    safe_print(f"Pitch: {args.pitch:+d}")
    safe_print(f"RVC server: {args.rvc_url}")

    await synth_edge(text)
    safe_print(f"TTS generated: {SRC_WAV}")

    await rvc_convert(args.rvc_url, args.pitch)
    safe_print(f"Output: {OUT_WAV.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
