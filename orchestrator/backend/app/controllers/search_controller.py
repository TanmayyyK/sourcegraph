from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.database import get_db
from app.core.auth import require_auditor
from app.models.schemas import SourcePacket
from app.services.similarity_service import similarity_service

router = APIRouter(prefix="/search", tags=["Search"])

@router.post("/suspect", status_code=status.HTTP_200_OK)
async def process_suspect_inference(
    packet: SourcePacket,
    role: str = Depends(require_auditor),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Workflow 2 (AUDITOR):
    Accepts suspected media vectors from external ingestion nodes 
    and triggers a PGVector KNN search against the "Golden Library"
    without actually inserting the suspect payload to the master node table permanently.
    """
    try:
        if not packet.visual_frames and not packet.text_frames:
             raise HTTPException(status_code=400, detail="Empty frame packet received.")

        visual_query = packet.visual_frames[0].vector if packet.visual_frames else [0.0]*512
        text_query = packet.text_frames[0].vector if packet.text_frames else [0.0]*384

        matches = await similarity_service.execute_knn_inference(
            db=db,
            query_visual=visual_query,
            query_text=text_query,
            limit=1
        )

        if not matches:
             return {"message": "No matches found.", "verdict": "CLEAN"}

        top_match = matches[0]
        verdict = "PIRACY_DETECTED" if top_match["fused_score"] >= 0.85 else ("SUSPICIOUS" if top_match["fused_score"] >= 0.60 else "CLEAN")

        return {
            "verdict": verdict,
            "target_golden_id": top_match["asset_id"],
            "matched_timestamp": top_match["timestamp"],
            "fused_confidence": top_match["fused_score"],
            "details": top_match
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference execution failed: {str(e)}")
