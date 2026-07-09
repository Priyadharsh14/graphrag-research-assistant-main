from app.services.pdf_processor import chunk_document, file_sha256, parse_pdf


def test_parse_pdf_extracts_pages_and_abstract(sample_pdf_path):
    doc = parse_pdf(sample_pdf_path)
    assert len(doc.pages) == 1
    assert doc.abstract is not None
    assert "retrieval-augmented generation" in doc.abstract.lower()


def test_chunk_document_produces_nonempty_chunks(sample_pdf_path):
    doc = parse_pdf(sample_pdf_path)
    chunks = chunk_document(doc, chunk_size_tokens=20, overlap_tokens=5)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.text.strip() != ""
        assert c.page == 1


def test_chunk_document_empty_pdf_returns_no_chunks():
    from app.services.pdf_processor import ParsedDocument, ParsedPage

    empty_doc = ParsedDocument(pages=[ParsedPage(1, "")], full_text="", title=None, abstract=None)
    chunks = chunk_document(empty_doc)
    assert chunks == []


def test_file_sha256_is_deterministic(sample_pdf_path):
    h1 = file_sha256(sample_pdf_path)
    h2 = file_sha256(sample_pdf_path)
    assert h1 == h2
    assert len(h1) == 64
