import pytest

from app.evidence_graph import (
    EvidenceBundle,
    EvidenceCard,
    GraphEdge,
    GraphNode,
    validate_bundle,
    validate_edge,
)


def test_bundle_requires_source_quotes_primary_and_unique_roles():
    bundle = EvidenceBundle(cards=[EvidenceCard(source_id="source-001", role="primary", quote="Kaynakta yeterince uzun doğrulanmış bir cümle bulunuyor.")], reviewer="Öğretmen", reason="PDF ile karşılaştırıldı ve soru için doğrudan kanıt olduğu görüldü.", approved=True)
    validate_bundle(bundle, {"source-001": "Kaynakta yeterince uzun doğrulanmış bir cümle bulunuyor."})
    with pytest.raises(ValueError):
        validate_bundle(bundle, {"source-001": "Başka metin"})


def test_graph_edge_cannot_be_source_free_or_self_referential():
    nodes = {"olay": GraphNode(id="olay", label="Bir olay", kind="olay"), "tarih": GraphNode(id="tarih", label="1071", kind="tarih_donem")}
    edge = GraphEdge(id="olay-tarih", from_node="olay", to_node="tarih", relation="gerceklesti_tarih", source_id="source-001", quote="Bir olay 1071 yılında gerçekleştiği kaynakta belirtilir.", approved=True)
    validate_edge(edge, nodes, {"source-001": "Bir olay 1071 yılında gerçekleştiği kaynakta belirtilir."})
    with pytest.raises(ValueError):
        GraphEdge(id="self", from_node="olay", to_node="olay", relation="iliskilidir", source_id="source-001", quote="Bir olay 1071 yılında gerçekleştiği kaynakta belirtilir.", approved=True)
