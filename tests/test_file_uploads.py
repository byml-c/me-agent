from __future__ import annotations


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
