import os
import json
import requests
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from overwatch_logic import OverwatchNode

load_dotenv()

TANMAY_URL = os.getenv("TANMAY_URL", "http://100.69.253.89:8000/api/v1/webhooks/vector")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8002"))

app = FastAPI(title="Context ML Node (Yug) - Overwatch")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

node = OverwatchNode()


def _parse_metadata(raw: str) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        print(f"WARNING: Could not parse metadata: {raw!r}")
        return {}


def _forward_to_orchestrator(payload: dict, label: str = "") -> None:
    try:
        secret = os.getenv("WEBHOOK_SECRET", "change-me-in-production")
        headers = {"X-Webhook-Secret": secret}
        resp = requests.post(TANMAY_URL, json=payload, headers=headers, timeout=10)
        if resp.status_code not in (200, 202):
            print(f"REJECTED {label} ({resp.status_code}): {resp.text}")
        else:
            print(f"ACCEPTED {label} ({resp.status_code})")
    except requests.exceptions.ConnectionError:
        print(f"UNREACHABLE: {label}")
    except requests.exceptions.Timeout:
        print(f"TIMEOUT: {label}")
    except Exception as exc:
        print(f"ERROR forwarding {label}: {exc}")


@app.get("/")
async def health_check():
    return {
        "status": "online",
        "node": "Yug-RTX2050",
        "protocol": "Anti-Gravity Context Managed",
        "task": "Multimodal Overwatch",
    }


@app.post("/embed/audio")
async def process_audio(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    metadata: str = Form("{}"),
):
    contents = await audio.read()
    meta = _parse_metadata(metadata)
    packet_id = meta.get("packet_id", "unknown")
    video_name = meta.get("video_name", "unknown")
    temp_wav_path = f"temp_audio_{packet_id}.wav"

    with open(temp_wav_path, "wb") as f:
        f.write(contents)

    print(f"AUDIO RECEIVED: {audio.filename} (video: {video_name})")

    def _run_audio_pipeline(wav_path: str) -> None:
        from audio_engine import AudioEngine
        try:
            engine = AudioEngine()
            golden_packet = engine.transcribe(wav_path)

            if not isinstance(golden_packet, dict):
                golden_packet = {"raw": str(golden_packet)}

            full_script = golden_packet.get("full_script", "").strip()
            embed_text = full_script if full_script else "Empty Context"

            if node._minilm is None:
                node.prepare_visual_phase()

            vector = node._minilm.encode(embed_text, convert_to_tensor=False).tolist()

            payload = {
                "packet_id": packet_id,
                "timestamp": 0.0,
                "text_vector": vector,
                "source_node": "Yug-RTX2050",
                "type": "audio_transcript",
                "full_script": full_script,
                "video_name": video_name,
            }

            print("SENDING audio transcript to orchestrator")
            _forward_to_orchestrator(payload, label="audio_transcript")

        except Exception as exc:
            print(f"AUDIO ENGINE ERROR: {exc}")
        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError as exc:
                    print(f"Could not delete temp WAV: {exc}")

        try:
            node.prepare_visual_phase()
        except Exception as exc:
            print(f"prepare_visual_phase error: {exc}")

    background_tasks.add_task(_run_audio_pipeline, temp_wav_path)
    return {"status": "accepted", "message": "Audio dispatched to background pipeline."}


@app.post("/embed/text")
async def process_frame(
    image: UploadFile = File(...),
    metadata: str = Form("{}"),
):
    meta = _parse_metadata(metadata)
    packet_id = meta.get("packet_id", "unknown")
    video_name = meta.get("video_name", "unknown")
    frame_index = meta.get("frame_index", -1)
    video_ts = meta.get("video_timestamp_s", -1)

    contents = await image.read()
    visual_results = node.run_visual_phase(contents)

    if visual_results.get("ocr_text"):
        print(
            f"OCR frame {frame_index} | {video_name} | "

            f"{packet_id[:8]} -> {visual_results['ocr_text'][:120]}"
        )

    valid_timestamp = float(video_ts) if float(video_ts) >= 0 else float(frame_index)

    source_packet = {
        "packet_id": packet_id,
        "timestamp": valid_timestamp,
        "text_vector": visual_results.get("vector"),
        "source_node": "Yug-RTX2050",
    }

    _forward_to_orchestrator(source_packet, label=f"frame {frame_index}")

    return source_packet


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)