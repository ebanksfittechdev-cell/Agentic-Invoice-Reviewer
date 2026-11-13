"""
test_upload.py — tests for the invoice upload pipeline.

Gemini extraction is mocked so no API key is needed.
Tests cover: file validation, total check → status, discrepancy hook wiring,
and the list/detail endpoints.
"""

import io
import json
import pytest
from unittest.mock import patch

from tests.conftest import make_user, make_vendor
from db import Invoice, InvoiceLine


MOCK_EXTRACTION = {
    "invoice_number": "INV-TEST-001",
    "invoice_date": "2026-11-01",
    "total": 20.00,
    "lines": [
        {
            "line_type": "item",
            "item_code": "ITEM-1",
            "description": "Test Item",
            "quantity": 2,
            "unit": "case",
            "unit_price": 10.00,
            "line_total": 20.00,
            "handwritten_note": "rec'd 2",
        }
    ],
}


def _login_new(client, email="upload@store.com"):
    client.post("/api/auth/register", json={
        "email": email, "password": "pw", "store_name": "Upload Store"
    })


def _upload(client, extraction=None, filename="invoice.jpg"):
    payload = extraction or MOCK_EXTRACTION
    with patch("invoices.routes.extract_invoice", return_value=payload):
        return client.post(
            "/api/invoices/upload",
            data={"file": (io.BytesIO(b"fake-image-bytes"), filename)},
            content_type="multipart/form-data",
        )


class TestUploadValidation:
    def test_requires_auth(self, client, db):
        resp = client.post("/api/invoices/upload",
                           data={"file": (io.BytesIO(b"x"), "inv.jpg")},
                           content_type="multipart/form-data")
        assert resp.status_code == 401

    def test_no_file_field_returns_400(self, client, db):
        _login_new(client)
        resp = client.post("/api/invoices/upload",
                           data={}, content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_unsupported_mime_returns_415(self, client, db):
        _login_new(client)
        with patch("invoices.extractor.extract_invoice", return_value=MOCK_EXTRACTION):
            resp = client.post(
                "/api/invoices/upload",
                data={"file": (io.BytesIO(b"bad"), "invoice.txt")},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 415


class TestUploadPipeline:
    def test_successful_upload_returns_201(self, client, db):
        _login_new(client)
        resp = _upload(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["invoice_number"] == "INV-TEST-001"
        assert data["status"] == "checked"
        assert data["line_count"] == 1

    def test_lines_persisted(self, app, client, db):
        _login_new(client)
        resp = _upload(client)
        invoice_id = resp.get_json()["invoice_id"]
        with app.app_context():
            lines = InvoiceLine.query.filter_by(invoice_id=invoice_id).all()
            assert len(lines) == 1
            assert lines[0].item_code == "ITEM-1"
            assert float(lines[0].unit_price) == pytest.approx(10.00)

    def test_total_mismatch_sets_needs_review(self, client, db):
        _login_new(client)
        bad_extraction = {**MOCK_EXTRACTION, "total": 99.99}  # doesn't match sum of lines
        resp = _upload(client, extraction=bad_extraction)
        assert resp.status_code == 201
        assert resp.get_json()["status"] == "needs_review"

    def test_extraction_failure_sets_needs_review(self, client, db):
        _login_new(client)
        from invoices.extractor import ExtractionError
        with patch("invoices.routes.extract_invoice",
                   side_effect=ExtractionError("API failed")):
            resp = client.post(
                "/api/invoices/upload",
                data={"file": (io.BytesIO(b"bad-bytes"), "invoice.jpg")},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "needs_review"


class TestInvoiceList:
    def test_list_requires_auth(self, client, db):
        assert client.get("/api/invoices/").status_code == 401

    def test_list_returns_own_invoices(self, client, db):
        _login_new(client)
        _upload(client)
        resp = client.get("/api/invoices/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["invoice_number"] == "INV-TEST-001"

    def test_list_scoped_to_user(self, client, db):
        """A second user must not see the first user's invoices."""
        _login_new(client, "first@store.com")
        _upload(client)
        client.post("/api/auth/logout")

        client.post("/api/auth/register", json={
            "email": "second@store.com", "password": "pw", "store_name": "S2"
        })
        resp = client.get("/api/invoices/")
        assert resp.get_json() == []


class TestInvoiceDetail:
    def test_detail_returns_lines_and_discrepancies(self, client, db):
        _login_new(client)
        resp = _upload(client)
        invoice_id = resp.get_json()["invoice_id"]
        resp = client.get(f"/api/invoices/{invoice_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "lines" in data
        assert "discrepancies" in data
        assert "pending_actions" in data

    def test_detail_other_user_returns_404(self, client, db):
        _login_new(client, "owner@store.com")
        resp = _upload(client)
        invoice_id = resp.get_json()["invoice_id"]
        client.post("/api/auth/logout")

        client.post("/api/auth/register", json={
            "email": "intruder@store.com", "password": "pw", "store_name": "Bad"
        })
        assert client.get(f"/api/invoices/{invoice_id}").status_code == 404
