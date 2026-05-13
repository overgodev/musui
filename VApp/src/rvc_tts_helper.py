"""Generate TTS audio with edge-tts."""
import argparse
import asyncio

import edge_tts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edge TTS helper")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("output", help="Output wav file path")
    parser.add_argument("--voice", default="th-TH-PremwadeeNeural", help="Edge voice name")
    parser.add_argument("--rate", default="+0%", help="Edge rate, e.g. +3%% or -2%%")
    parser.add_argument("--pitch", default="+0Hz", help="Edge pitch, e.g. +60Hz or -40Hz")
    parser.add_argument("--volume", default="+0%", help="Edge volume, e.g. +6%% or -2%%")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    communicate = edge_tts.Communicate(
        text=args.text,
        voice=args.voice,
        rate=args.rate,
        pitch=args.pitch,
        volume=args.volume,
    )
    await communicate.save(args.output)


if __name__ == "__main__":
    asyncio.run(main())
