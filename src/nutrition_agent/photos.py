"""保健食品照片的本機儲存：檔案放在 volume，檔名隨機；歸屬與存取檢查由 API 負責。"""

import uuid
from pathlib import Path

MAX_PHOTO_BYTES = 10 * 1024 * 1024

_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
)


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """依檔案內容（不信任上傳的檔名或 Content-Type）判斷 (mime, 副檔名)；不是支援的圖片回傳 None。"""
    for magic, mime, ext in _SIGNATURES:
        if data.startswith(magic):
            return mime, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


class PhotoStore:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def save(self, data: bytes, ext: str) -> str:
        self._root.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}{ext}"
        (self._root / name).write_bytes(data)
        return name

    def read(self, name: str) -> bytes:
        return (self._root / Path(name).name).read_bytes()

    def delete(self, name: str) -> None:
        (self._root / Path(name).name).unlink(missing_ok=True)
