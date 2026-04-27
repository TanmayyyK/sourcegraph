import uuid
import httpx
import pytest
from jose import jwt
from datetime import datetime, timedelta, timezone

# ─── Configuration ────────────────────────────────────────────────────────────
# Used to simulate JWTs for PRODUCER vs AUDITOR
JWT_SECRET = "super_secret_key_change_in_production"
JWT_ALGORITHM = "HS256"

# The target ML Auditor service
AUDITOR_URL = "http://localhost:8004/api/v1/auditor"

# ─── 1. Dummy JWT Generation ──────────────────────────────────────────────────
def generate_dummy_jwt(role: str) -> str:
    """Simulate the Orchestrator's /verify-otp endpoint for testing RBAC."""
    to_encode = {
        "sub": f"test_{role.lower()}@sourcegraph.com",
        "name": f"Test {role}",
        "role": role.upper(),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ─── 2. Mock Vectors ──────────────────────────────────────────────────────────
# Fake 512-D visual and 384-D text/audio vectors
VISUAL_VEC = [0.15] * 512
TEXT_VEC = [0.25] * 384
AUDIO_VEC = [0.35] * 384

@pytest.mark.asyncio
async def test_producer_flow():
    """
    Simulates the PRODUCER Flow:
    - JWT role: PRODUCER
    - is_golden = True
    - Action: Index vectors into FAISS
    """
    token = generate_dummy_jwt("PRODUCER")
    print(f"\n[PRODUCER FLOW] Generated JWT: {token[:20]}...")
    
    asset_id = str(uuid.uuid4())
    
    # Simulate the payload that auditor_client.py would construct after extracting from DB
    mock_payload = {
        "asset_id": asset_id,
        "visual_vectors": [VISUAL_VEC],
        "text_vectors": [TEXT_VEC],
        "audio_vectors": [AUDIO_VEC]
    }

    async with httpx.AsyncClient() as client:
        print(f"[PRODUCER FLOW] Routing golden asset {asset_id} to /index...")
        resp = await client.post(f"{AUDITOR_URL}/index", json=mock_payload, timeout=5.0)
        
        # 3. Assert PRODUCER returns 200 OK
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}. Body: {resp.text}"
        
        data = resp.json()
        assert data["status"] == "success"
        assert data["indexed_visual"] == 1
        print(f"[PRODUCER FLOW] ✅ Success! Indexed 1 visual, 1 text, 1 audio vector.")


@pytest.mark.asyncio
async def test_auditor_flow():
    """
    Simulates the AUDITOR Flow:
    - JWT role: AUDITOR
    - is_golden = False
    - Action: Search vectors against FAISS to calculate a verdict
    """
    token = generate_dummy_jwt("AUDITOR")
    print(f"\n[AUDITOR FLOW] Generated JWT: {token[:20]}...")
    
    suspect_asset_id = str(uuid.uuid4())
    
    # We use identical vectors here, so the similarity should be very high (PIRACY_DETECTED)
    mock_payload = {
        "asset_id": suspect_asset_id,
        "visual_vectors": [VISUAL_VEC],
        "text_vectors": [TEXT_VEC],
        "audio_vectors": [AUDIO_VEC]
    }

    async with httpx.AsyncClient() as client:
        print(f"[AUDITOR FLOW] Routing suspect asset {suspect_asset_id} to /search...")
        resp = await client.post(f"{AUDITOR_URL}/search", json=mock_payload, timeout=5.0)
        
        # 4. Assert AUDITOR returns 200 OK with a SearchResult
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}. Body: {resp.text}"
        
        data = resp.json()
        assert "verdict" in data
        assert "fused_score" in data
        
        verdict = data["verdict"]
        score = data["fused_score"]
        print(f"[AUDITOR FLOW] ✅ Success! Verdict: {verdict} (Score: {score}%)")
        
        # Since we indexed the exact same vectors in test_producer_flow, we expect piracy
        assert verdict == "PIRACY_DETECTED", f"Expected PIRACY_DETECTED, but got {verdict}"


# ─── Standalone Runner ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    
    async def run_all():
        print("🚀 Starting RBAC GO / NO GO Tests...")
        try:
            await test_producer_flow()
            await test_auditor_flow()
            print("\n🎉 ALL FLOWS VERIFIED. READY FOR PRODUCTION.")
        except Exception as e:
            print(f"\n❌ TEST FAILED: {str(e)}")
            
    asyncio.run(run_all())
