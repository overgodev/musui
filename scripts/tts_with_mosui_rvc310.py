import asyncio, pathlib, subprocess, sys, requests, edge_tts

ORCH = "http://localhost:8002/decide"
MODEL = pathlib.Path("voice model/mosui/mosui.pth")
INDEX = pathlib.Path("voice model/mosui/mosui.index")
SRC = pathlib.Path("artifacts/audio/src_edge.wav")
OUT = pathlib.Path("artifacts/audio/mosui_out.wav")

def fetch_reply():
    try:
        r = requests.post(ORCH, json={"author":{"author_id":"u1","display_name":"ปลาเผา"},
                                      "text":"วันนี้เล่นเกมอะไร","source":"youtube"}, timeout=10)
        r.raise_for_status()
        return r.json().get("reply_text_th") or "วันนี้เล่นเกมอะไร"
    except Exception:
        return "วันนี้เล่นเกมอะไร"

async def synth_edge(text):
    SRC.parent.mkdir(parents=True, exist_ok=True)
    await edge_tts.Communicate(text=text, voice="th-TH-PremwadeeNeural").save(str(SRC))

def run_rvc():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "rvc_python", "cli",
           "-i", str(SRC), "-o", str(OUT),
           "-mp", str(MODEL), "-de", "cpu",
           "-ip", str(INDEX), "-f0m", "pm", "-ir", "0.75", "-pro", "0.33"]
    subprocess.run(cmd, check=True)

def main():
    text = fetch_reply()
    print("Reply:", text)
    asyncio.run(synth_edge(text))
    run_rvc()
    print("Audio:", OUT.resolve())

if __name__ == "__main__":
    main()
