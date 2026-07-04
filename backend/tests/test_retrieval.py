from app.rag.retrieval import HybridRetriever
from app.rag.schemas import SourceChunk


def make_chunk(index: int, text: str) -> SourceChunk:
    return SourceChunk(
        id=f"c{index}",
        sourceId="s",
        title=f"chunk {index}",
        text=text,
        sourceType="text",
        fileName="sample.md",
        chunkIndex=index,
        sourceRef=f"para_{index}",
    )


def test_retriever_uses_inverted_candidates_without_losing_hits():
    chunks = [
        make_chunk(1, "ordinary introduction text"),
        make_chunk(2, "retrieval augmented generation citation grounding"),
        make_chunk(3, "expectation maximization likelihood"),
    ]
    retriever = HybridRetriever(chunks)

    hits = retriever.retrieve("citation grounding", top_k=2)

    assert hits
    assert hits[0].chunk.id == "c2"
    assert retriever._candidate_indexes(["citation", "grounding"])


def test_retriever_expands_query_and_attaches_adjacent_evidence():
    chunks = [
        make_chunk(1, "RAG systems ingest documents and prepare context."),
        make_chunk(2, "Grounding citations connect generated notes to source evidence."),
        make_chunk(3, "Review questions help students test grounded understanding."),
    ]
    for item in chunks:
        item.parentId = "sample-section"
        item.keywords = ["citations", "evidence"] if item.chunkIndex == 2 else []
    retriever = HybridRetriever(chunks)

    hits = retriever.retrieve("grounding", top_k=1, include_context=True)

    assert hits[0].chunk.id == "c2"
    assert "citations" in hits[0].expanded_query
    assert hits[0].evidence["before"]["sourceId"] == "c1"
    assert hits[0].evidence["after"]["sourceId"] == "c3"
