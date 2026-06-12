from __future__ import annotations


SIMPLE_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 55 >>
stream
BT /F1 24 Tf 72 720 Td (Me Agent PDF searchable text) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000241 00000 n 
0000000311 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
416
%%EOF
"""


def test_upload_binary_file_keeps_summary_and_download(client):
    response = client.post(
        "/files/upload",
        files={"file": ("diagram.png", b"\x89PNG\r\n\x1a\n\x00\x00binary", "image/png")},
        data={"description": "架构图截图"},
    )

    assert response.status_code == 200
    item = response.json()
    assert item["name"] == "diagram.png"
    assert item["media_type"] == "image/png"
    assert item["content"] == ""
    assert item["text_extracted"] is False
    assert item["size_bytes"] > 0
    assert item["download_url"].endswith(f"/files/{item['id']}/download")

    download = client.get(item["download_url"])
    assert download.status_code == 200
    assert download.content.startswith(b"\x89PNG")


def test_upload_pdf_extracts_text_for_library_search_and_keeps_original(client):
    response = client.post(
        "/files/upload",
        files={"file": ("notes.pdf", SIMPLE_PDF, "application/pdf")},
    )

    assert response.status_code == 200
    item = response.json()
    assert item["name"] == "notes.pdf"
    assert item["media_type"] == "application/pdf"
    assert item["text_extracted"] is True
    assert "Me Agent PDF searchable text" in item["content"]
    assert item["download_url"].endswith(f"/files/{item['id']}/download")

    entries = client.get("/library/entries", params={"query": "searchable", "kind": "file"}).json()
    assert any(entry["source_file_id"] == item["id"] for entry in entries)

    download = client.get(item["download_url"])
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")
