"""
╔══════════════════════════════════════════════════════════════════════╗
║  SourceGraph — Live Webhook Simulator (Data Feeder Role)             ║
║  Owner : Tanmay (Founder & Chief Architect)                          ║
║                                                                      ║
║  PURPOSE:                                                            ║
║    Simulates the pure "Data Feeder" ingestion flow.                  ║
║    1. Pings system health (3/3 nodes).                               ║
║    2. Streams 10-15 frames of raw vectors (Yug & Rohit).             ║
║    3. Sends final summary payloads for Yug, Rohit, AND YOGESH.       ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import uuid
import random
import requests
import base64
import json
import hmac
import hashlib
from concurrent.futures import ThreadPoolExecutor

TANMAY_WEBHOOK_URL = os.getenv("TANMAY_URL", "http://127.0.0.1:8000/api/v1/webhooks/feeder")
GOLDEN_UPLOAD_URL = os.getenv("GOLDEN_UPLOAD_URL", "http://127.0.0.1:8000/api/v1/golden/upload")
WEBHOOK_SECRET = "change-me-in-production"
JWT_SECRET = "super-secret-overwatch-key-change-in-prod"

NUM_FRAMES = random.randint(10, 15)
VECTOR_DIMENSIONS = 512
TEXT_VECTOR_DIMENSIONS = 384
START_TIME = time.time()

def fire_webhook(payload: dict, label: str):
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": WEBHOOK_SECRET
    }
    try:
        resp = requests.post(TANMAY_WEBHOOK_URL, json=payload, headers=headers, timeout=5)
        if resp.status_code in (200, 202):
            print(f"✅ [SUCCESS] {label}")
        else:
            print(f"⚠️ [REJECTED] {label} - {resp.status_code}")
            print(resp.text)
    except requests.exceptions.ConnectionError:
        print(f"❌ [UNREACHABLE] Is orchestrator running at {TANMAY_WEBHOOK_URL}?")
        time.sleep(1)

def generate_mock_vector() -> list[float]:
    return [round(random.uniform(-1.0, 1.0), 5) for _ in range(VECTOR_DIMENSIONS)]

def generate_mock_text_vector() -> list[float]:
    return [round(random.uniform(-1.0, 1.0), 5) for _ in range(TEXT_VECTOR_DIMENSIONS)]

def generate_producer_jwt() -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": "simulator_script",
        "role": "PRODUCER",
        "exp": int(time.time()) + 3600
    }
    b64_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    
    signature = hmac.new(
        JWT_SECRET.encode(),
        f"{b64_header}.{b64_payload}".encode(),
        hashlib.sha256
    ).digest()
    b64_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    return f"{b64_header}.{b64_payload}.{b64_signature}"

def seed_database() -> str:
    print("\n🌱 Seeding database with dummy asset...")
    token = generate_producer_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("dummy_stream_asset.mp4", b"dummy video bytes", "video/mp4")}
    
    try:
        resp = requests.post(GOLDEN_UPLOAD_URL, headers=headers, files=files, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        asset_id = data.get("asset_id")
        print(f"✅ [SEEDED] Database created Asset ID: {asset_id}")
        return asset_id
    except requests.exceptions.RequestException as e:
        print(f"❌ [SEED FAILED] Could not contact /upload API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        print("   Falling back to local UUID generator...")
        return str(uuid.uuid4())

def simulate_feeder_stream():
    asset_id = seed_database()
    packet_id = str(asset_id)
    video_name = f"golden_source_asset_{random.randint(100, 999)}.mp4"
    
    print("=" * 60)
    print(f"🚀 STARTING DATA FEEDER STREAM: {video_name}")
    print(f"📦 Packet ID: {packet_id}")
    print("=" * 60)

    # 1. LIVE PING (SYSTEM HEALTH)
    print("\n📡 Pinging System Health...")
    health_payload = {
        "packet_id": packet_id,
        "type": "system_ping",
        "nodes_online": "3/3",
        "services": {
            "ingest_api": "OK",
            "vision_engine": "OK",
            "text_processor": "OK",
            "orchestrator": "OK"
        }
    }
    fire_webhook(health_payload, "System Health Ping")
    time.sleep(1.5)

    # 2. STREAMING FRAMES (YUG & ROHIT)
    print(f"\n🌊 Streaming {NUM_FRAMES} frames...")
    total_ocr_chunks = 0
    total_bounding_boxes = 0

    with ThreadPoolExecutor(max_workers=4) as executor:
        for frame_idx in range(1, NUM_FRAMES + 1):
            timestamp_s = float(frame_idx)
            
            chunks = random.randint(10, 45)
            boxes = chunks * random.randint(4, 8)
            total_ocr_chunks += chunks
            total_bounding_boxes += boxes

            rohit_payload = {
                "packet_id": packet_id,
                "type": "frame_vision",
                "timestamp": timestamp_s,
                "source_node": "ml_vision",
                "visual_vector": generate_mock_vector()
            }
            
            yug_payload = {
                "packet_id": packet_id,
                "type": "frame_text",
                "timestamp": timestamp_s,
                "source_node": "ml_context",
                "chunks_extracted": chunks,
                "boxes_mapped": boxes,
                "ocr_text": f"Sample OCR text for frame {frame_idx}",
                "text_vector": generate_mock_text_vector(),
            }
            
            executor.submit(fire_webhook, rohit_payload, f"Rohit Frame {frame_idx}")
            executor.submit(fire_webhook, yug_payload, f"Yug Frame {frame_idx}")
            time.sleep(random.uniform(0.4, 0.9))

    # 3. FINAL AGGREGATED SUMMARIES (YUG, ROHIT, & YOGESH)
    print("\n🏁 Finalizing Data Feeder Indexes...")
    time.sleep(2)
    
    total_time_taken = round(time.time() - START_TIME, 2)

    # A. Rohit's Summary
    rohit_final_summary = {
        "packet_id": packet_id,
        "type": "vision_final_summary",
        "source_node": "ml_vision",
        "metrics": {
            "vector_embeddings": NUM_FRAMES,
            "dimensionality": "512-D mapped",
            "index_status": "Indexed for DB",
            "node_time_s": total_time_taken - 1.5
        }
    }

    # B. Yug's Summary
    yug_final_summary = {
        "packet_id": packet_id,
        "type": "text_final_summary",
        "source_node": "ml_context",
        "metrics": {
            "ocr_text_chunks": total_ocr_chunks,
            "bounding_boxes_mapped": total_bounding_boxes,
            "node_time_s": total_time_taken - 1.5
        }
    }

    # C. YOGESH'S SUMMARY (The Master Pipeline Status)
    yogesh_final_summary = {
        "packet_id": packet_id,
        "type": "pipeline_final_summary",
        "source_node": "Yogesh-M2",
        "metrics": {
            "total_frames_extracted": NUM_FRAMES,
            "successful_broadcasts": NUM_FRAMES,
            "failed_broadcasts": 0,
            "total_pipeline_time_s": total_time_taken
        }
    }

    fire_webhook(yug_final_summary, "Yug Final Summary")
    fire_webhook(rohit_final_summary, "Rohit Final Summary")
    fire_webhook(yogesh_final_summary, "Yogesh Master Summary") # NEW!
    
    print("\n✅ DATA FEEDER STREAM COMPLETE.")

if __name__ == "__main__":
    simulate_feeder_stream()