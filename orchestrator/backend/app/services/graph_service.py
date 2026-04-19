"""
Propagation Graph Builder — visualizes piracy lineage.

When a match is detected between a Golden Source and a Suspect,
this module builds a directed graph showing:
  - PRIMARY_SOURCE → the original protected content
  - PIRATE_NODE    → the suspect infringing content
  - RELAY          → intermediate nodes (future: re-uploaders)

Confidence Propagation:
  child_confidence = parent_confidence × edge_weight

The graph is JSON-serializable for the frontend dashboard.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.config import settings
from app.core.logger import get_logger
from app.models.schemas import (
    MatchResult,
    PropagationEdge,
    PropagationGraph,
    PropagationNode,
)

logger = get_logger("sourcegraph.graph")


class PropagationGraphBuilder:
    """
    Builds a directed graph of piracy propagation.

    Phase 1: Simple 2-node graphs (source → pirate).
    Phase 2: Multi-hop graphs with relay nodes.
    """

    def build_graph(self, match: MatchResult) -> PropagationGraph:
        """
        Construct a PropagationGraph from a single match result.

        The source node gets confidence = match.confidence.
        The pirate node gets a propagated confidence:
          pirate_confidence = source_confidence × edge_weight

        Edge weight = fused_score (how strong the match is).
        """
        source_confidence = match.confidence
        edge_weight = match.fused_score

        # Propagation: child_confidence = parent_confidence × edge_weight
        pirate_confidence = min(source_confidence * edge_weight, 1.0)

        source_node = PropagationNode(
            node_id=match.source_id,
            label=match.source_name,
            role="PRIMARY_SOURCE",
            confidence=source_confidence,
        )

        pirate_node = PropagationNode(
            node_id=match.suspect_id,
            label=match.suspect_video,
            role="PIRATE_NODE",
            confidence=pirate_confidence,
        )

        edge = PropagationEdge(
            from_node=match.source_id,
            to_node=match.suspect_id,
            weight=edge_weight,
            relationship="suspected_piracy",
        )

        graph = PropagationGraph(
            nodes=[source_node, pirate_node],
            edges=[edge],
            primary_source_id=match.source_id,
            pirate_node_ids=[match.suspect_id],
        )

        logger.info(
            f"[GRAPH] 📊 Built propagation graph: "
            f"{match.source_name} → {match.suspect_video} "
            f"(edge_weight={edge_weight:.4f}, "
            f"pirate_confidence={pirate_confidence:.4f})"
        )

        return graph

    def build_multi_hop_graph(
        self,
        matches: list[MatchResult],
    ) -> PropagationGraph:
        """
        Build a multi-hop propagation graph from multiple matches.

        Combines individual match graphs, deduplicating nodes and
        propagating confidence through the chain:
          A → B → C  means C's confidence = A.conf × AB.weight × BC.weight

        Phase 2: This will support full graph traversal.
        """
        all_nodes: dict[UUID, PropagationNode] = {}
        all_edges: list[PropagationEdge] = []
        pirate_ids: list[UUID] = []
        primary_source_id: UUID | None = None

        for match in matches:
            sub_graph = self.build_graph(match)

            for node in sub_graph.nodes:
                if node.node_id not in all_nodes:
                    all_nodes[node.node_id] = node
                else:
                    # Update confidence if higher
                    existing = all_nodes[node.node_id]
                    if node.confidence > existing.confidence:
                        all_nodes[node.node_id] = node

            all_edges.extend(sub_graph.edges)
            pirate_ids.extend(sub_graph.pirate_node_ids)

            if primary_source_id is None:
                primary_source_id = sub_graph.primary_source_id

        # Propagate confidence through edges (BFS-style)
        self._propagate_confidence(all_nodes, all_edges)

        return PropagationGraph(
            nodes=list(all_nodes.values()),
            edges=all_edges,
            primary_source_id=primary_source_id or uuid4(),
            pirate_node_ids=list(set(pirate_ids)),
        )

    def _propagate_confidence(
        self,
        nodes: dict[UUID, PropagationNode],
        edges: list[PropagationEdge],
    ) -> None:
        """
        BFS confidence propagation through the graph.
        child_confidence = parent_confidence × edge_weight
        """
        # Build adjacency
        adjacency: dict[UUID, list[tuple[UUID, float]]] = {}
        for edge in edges:
            adjacency.setdefault(edge.from_node, []).append(
                (edge.to_node, edge.weight)
            )

        # Find roots (nodes with no incoming edges)
        targets = {e.to_node for e in edges}
        sources = {e.from_node for e in edges}
        roots = sources - targets

        # BFS from roots
        visited: set[UUID] = set()
        queue: list[UUID] = list(roots)

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            current_node = nodes.get(current_id)
            if current_node is None:
                continue

            for child_id, weight in adjacency.get(current_id, []):
                child_node = nodes.get(child_id)
                if child_node is None:
                    continue

                propagated = min(current_node.confidence * weight, 1.0)
                # Use the propagated confidence if it's higher
                if propagated > child_node.confidence:
                    nodes[child_id] = PropagationNode(
                        node_id=child_node.node_id,
                        label=child_node.label,
                        role=child_node.role,
                        confidence=propagated,
                    )

                queue.append(child_id)

    @staticmethod
    def calculate_confidence(match: MatchResult) -> float:
        """
        Bayesian-inspired confidence score combining all signals.

        conf = fused_score × (1 - uncertainty)
        where uncertainty decreases as more signal types are non-zero.
        """
        signals_present = sum([
            match.visual_score > 0.1,
            match.text_score > 0.1,
            match.temporal_score > 0.1,
        ])

        # More signals → less uncertainty
        uncertainty = max(0.0, 1.0 - (signals_present * 0.25))
        confidence = match.fused_score * (1.0 - uncertainty)

        return min(confidence, 1.0)
