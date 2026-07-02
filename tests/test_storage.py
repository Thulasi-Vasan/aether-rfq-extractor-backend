from pathlib import Path

from app.services.storage import document_id_from_sha256, sha256_file


def test_document_id_from_sha256_uses_stable_prefix() -> None:
    digest = "a" * 64
    assert document_id_from_sha256(digest) == "a" * 16


def test_sha256_file(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("hello", encoding="utf-8")
    assert sha256_file(path) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
