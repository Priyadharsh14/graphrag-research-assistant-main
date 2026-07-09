import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")

# The sandbox test environment doesn't need real embedding models loaded —
# stub sentence-transformers so unit tests stay fast and dependency-light.
if "sentence_transformers" not in sys.modules:
    fake_module = types.ModuleType("sentence_transformers")

    class _FakeSentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, texts, **kwargs):
            import numpy as np
            return np.zeros((len(texts), 384))

    fake_module.SentenceTransformer = _FakeSentenceTransformer
    sys.modules["sentence_transformers"] = fake_module

import pytest


@pytest.fixture
def sample_pdf_path(tmp_path):
    import fitz

    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Abstract\nThis paper studies retrieval-augmented generation.\n\n1. Introduction\nRAG combines retrieval with generation.")
    doc.save(str(path))
    doc.close()
    return str(path)
