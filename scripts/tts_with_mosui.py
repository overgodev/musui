import json, requests, pathlib
from tts_with_rvc_onnx import TTSWithRVC  # provided by the pip install

BASE = "http://localhost:8002/decide"
MODEL = pathlib.Path("voice model/mosui/mosui.pth")
INDEX = pathlib.Path("voice model/mosui/mosui.index")
OUTPUT = pathlib.Path("artifacts/audio/mosui_out.wav")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

resp = requests.post(
    BASE,
    json={
        "author": {"author_id": "u1", "display_name": "ปลาเผา"},
        "text": "วันนี้เล่นเกมอะไร",
        "source": "youtube",
    },
    timeout=15,
)
reply = resp.json().get("reply_text_th")
assert reply, f"no reply: {resp.text}"

tts = TTSWithRVC(
    model_path=str(MODEL),
    index_path=str(INDEX),
    # f0_method can be 'rmvpe', 'pm', 'dio', or 'harvest'; pm is lightest CPU
    f0_method="pm",
    device="cpu",
)
tts.tts_to_file(
    text=reply,
    output_path=str(OUTPUT),
    # you can tweak these:
    sdp_ratio=0.2,
    index_rate=0.75,
    protect=0.33,
)
print(f"Reply: {reply}")
print(f"Audio: {OUTPUT}")
