"""Edge TTS + local RVC conversion on CPU."""
import argparse
import asyncio
import os
import pathlib
import tempfile

import edge_tts
import torch.serialization
from fairseq.data.dictionary import Dictionary
from rvc_python.infer import RVCInference


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local CPU RVC TTS helper")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("output", help="Final output wav path")
    parser.add_argument("--model-path", required=True, help="Path to RVC .pth model")
    parser.add_argument("--index-path", default="", help="Optional path to RVC .index")
    parser.add_argument("--voice", default="th-TH-PremwadeeNeural", help="Edge TTS voice")
    parser.add_argument("--rate", default="+0%", help="Edge TTS rate")
    parser.add_argument("--edge-pitch", default="+0Hz", help="Edge TTS pitch")
    parser.add_argument("--volume", default="+0%", help="Edge TTS volume")
    parser.add_argument("--rvc-pitch", type=int, default=0, help="RVC transpose semitones")
    parser.add_argument("--f0method", default="harvest", help="RVC f0 method")
    parser.add_argument("--index-rate", type=float, default=0.9, help="RVC index rate")
    parser.add_argument("--protect", type=float, default=0.28, help="RVC protect")
    parser.add_argument("--rms-mix-rate", type=float, default=0.9, help="RVC rms mix rate")
    return parser.parse_args()


def clamp01(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


async def synth_edge(text: str, wav_path: str, voice: str, rate: str, pitch: str, volume: str) -> None:
    await edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
    ).save(wav_path)


def run_rvc(
    src_wav: str,
    out_wav: str,
    model_path: str,
    index_path: str,
    rvc_pitch: int,
    f0method: str,
    index_rate: float,
    protect: float,
    rms_mix_rate: float,
) -> None:
    if hasattr(torch.serialization, "add_safe_globals"):
        torch.serialization.add_safe_globals([Dictionary])

    resolved_index = index_path if index_path and pathlib.Path(index_path).exists() else ""

    rvc = RVCInference(device="cpu:0", version="v2")
    if hasattr(rvc, "config") and hasattr(rvc.config, "is_half"):
        rvc.config.is_half = False
    if hasattr(rvc, "vc") and hasattr(rvc.vc, "is_half"):
        rvc.vc.is_half = False

    rvc.load_model(model_path, version="v2", index_path=resolved_index)
    rvc.set_params(
        f0up_key=rvc_pitch,
        f0method=f0method,
        index_rate=clamp01(index_rate) if resolved_index else 0.0,
        protect=clamp01(protect),
        rms_mix_rate=clamp01(rms_mix_rate),
    )
    rvc.infer_file(src_wav, out_wav)


def main() -> None:
    args = parse_args()
    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    temp_src = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_src_path = temp_src.name
    temp_src.close()

    try:
        asyncio.run(
            synth_edge(
                text=args.text,
                wav_path=temp_src_path,
                voice=args.voice,
                rate=args.rate,
                pitch=args.edge_pitch,
                volume=args.volume,
            )
        )
        run_rvc(
            src_wav=temp_src_path,
            out_wav=str(out_path),
            model_path=args.model_path,
            index_path=args.index_path,
            rvc_pitch=args.rvc_pitch,
            f0method=args.f0method,
            index_rate=args.index_rate,
            protect=args.protect,
            rms_mix_rate=args.rms_mix_rate,
        )
    finally:
        try:
            os.unlink(temp_src_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
