"""
Thin requests-based client for the FastAPI backend. Every Streamlit page
goes through this module rather than calling `requests` directly, so the
base URL, timeouts, and error handling live in exactly one place.
"""
from __future__ import annotations

import os

import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
DEFAULT_TIMEOUT = 120


class APIError(Exception):
    """Raised when the backend returns a non-2xx response, with the detail
    message extracted so pages can show something useful instead of a
    raw stack trace."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


def _handle(resp: requests.Response):
    if resp.ok:
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.content
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    raise APIError(resp.status_code, str(detail))


# --- Papers / Upload & Library ---
def upload_paper(file_bytes: bytes, filename: str) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/papers/upload",
        files={"file": (filename, file_bytes, "application/pdf")},
        timeout=DEFAULT_TIMEOUT,
    )
    return _handle(resp)


def list_papers() -> list[dict]:
    resp = requests.get(f"{API_BASE_URL}/papers", timeout=DEFAULT_TIMEOUT)
    return _handle(resp)


def get_paper(paper_id: str) -> dict:
    resp = requests.get(f"{API_BASE_URL}/papers/{paper_id}", timeout=DEFAULT_TIMEOUT)
    return _handle(resp)


def get_job_status(job_id: str) -> dict:
    resp = requests.get(f"{API_BASE_URL}/papers/jobs/{job_id}", timeout=DEFAULT_TIMEOUT)
    return _handle(resp)


def delete_paper(paper_id: str) -> None:
    resp = requests.delete(f"{API_BASE_URL}/papers/{paper_id}", timeout=DEFAULT_TIMEOUT)
    if not resp.ok:
        _handle(resp)


def retry_ingestion(paper_id: str) -> dict:
    resp = requests.post(f"{API_BASE_URL}/papers/{paper_id}/retry", timeout=DEFAULT_TIMEOUT)
    return _handle(resp)


# --- Research Chat ---
def ask_question(question: str, paper_ids: list[str] | None = None) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/chat",
        json={"question": question, "paper_ids": paper_ids},
        timeout=DEFAULT_TIMEOUT,
    )
    return _handle(resp)


# --- Research analysis ---
def literature_review(topic: str, paper_ids: list[str] | None = None) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/literature-review",
        json={"topic": topic, "paper_ids": paper_ids},
        timeout=DEFAULT_TIMEOUT,
    )
    return _handle(resp)


def compare_papers(paper_ids: list[str], aspects: list[str] | None = None) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/compare-papers",
        json={"paper_ids": paper_ids, "aspects": aspects},
        timeout=DEFAULT_TIMEOUT,
    )
    return _handle(resp)


def gap_analysis(paper_ids: list[str] | None = None, focus_area: str | None = None) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/gap-analysis",
        json={"paper_ids": paper_ids, "focus_area": focus_area},
        timeout=DEFAULT_TIMEOUT,
    )
    return _handle(resp)


@st.cache_data(ttl=5, show_spinner=False)
def list_papers_cached() -> list[dict]:
    """Short-TTL cache so pages that just need the paper list for a dropdown
    don't all hammer the API on every widget interaction."""
    return list_papers()
