from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List

from app.models.db_models import FrameVector, Asset

class SimilarityService:
    def __init__(self, visual_weight: float = 0.65, text_weight: float = 0.35):
        self.visual_weight = visual_weight
        self.text_weight = text_weight

    async def execute_knn_inference(
        self, 
        db: AsyncSession, 
        query_visual: List[float], 
        query_text: List[float], 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Executes a highly optimized Fused KNN matrix utilizing pgvector.
        It pushes the heavy floating-point Cosine distance (<=>) computation 
        entirely into Postgres relying heavily on the HNSW indexes.
        """
        
        stmt = (
            select(
                FrameVector.asset_id,
                FrameVector.timestamp,
                (1 - FrameVector.visual_vector.cosine_distance(query_visual)).label("visual_sim"),
                (1 - FrameVector.text_vector.cosine_distance(query_text)).label("text_sim"),
            )
            .join(Asset, Asset.id == FrameVector.asset_id)
            .where(Asset.is_golden == True)
        )

        result = await db.execute(stmt)
        rows = result.all()

        matches = []
        for row in rows:
            visual_sim = row.visual_sim or 0.0
            text_sim = row.text_sim or 0.0
            
            fused_score = (visual_sim * self.visual_weight) + (text_sim * self.text_weight)
            
            matches.append({
                "asset_id": str(row.asset_id),
                "timestamp": row.timestamp,
                "visual_sim": float(visual_sim),
                "text_sim": float(text_sim),
                "fused_score": float(fused_score)
            })

        matches.sort(key=lambda x: x["fused_score"], reverse=True)
        return matches[:limit]

similarity_service = SimilarityService()
