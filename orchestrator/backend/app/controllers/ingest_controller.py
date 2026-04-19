from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.database import get_db
from app.core.auth import require_producer
from app.models.schemas import SourcePacket
from app.models.db_models import Asset, FrameVector

router = APIRouter(prefix="/ingest", tags=["Ingest"])

@router.post("/golden", status_code=status.HTTP_201_CREATED)
async def register_golden_asset(
    packet: SourcePacket,
    role: str = Depends(require_producer),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Workflow 1 (PRODUCER):
    Registers a master footprint directly into the PostgreSQL Database.
    This effectively creates the 'Golden Asset' profile. All subsequent inference
    operations will map against these stored truth vectors.
    """
    try:
        new_asset = Asset(
            title=getattr(packet, 'metadata', {}).get("title", f"Golden Asset {packet.source_id}"),
            is_golden=True
        )
        db.add(new_asset)
        await db.flush()

        frames_to_insert = []
        for v_frame in packet.visual_frames:
            timestamp = v_frame.timestamp
            t_frame = next((t for t in packet.text_frames if t.timestamp == timestamp), None)
            
            t_vector = t_frame.vector if t_frame else [0.0] * 384
            v_vector = v_frame.vector
            
            frames_to_insert.append(
                FrameVector(
                    asset_id=new_asset.id,
                    timestamp=timestamp,
                    visual_vector=v_vector,
                    text_vector=t_vector
                )
            )

        db.add_all(frames_to_insert)
        await db.commit()

        return {"message": "Golden source registered.", "asset_id": str(new_asset.id), "frame_count": len(frames_to_insert)}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Insertion Failed: {str(e)}")
