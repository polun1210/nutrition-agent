"""測試用的真實小圖：用 Pillow 產生，上傳後才通得過解碼與正規化。"""

import io
import struct
import zlib

from PIL import ExifTags, Image, ImageDraw

# 解碼後讀得出中繼資料的那幾項，用來確認正規化後都不見了。
PHOTO_GPS = {
    ExifTags.GPS.GPSLatitudeRef: "N",
    ExifTags.GPS.GPSLatitude: (25.0, 2.0, 0.0),
    ExifTags.GPS.GPSLongitudeRef: "E",
    ExifTags.GPS.GPSLongitude: (121.0, 33.0, 0.0),
}


def make_image(
    fmt: str = "JPEG",
    size: tuple[int, int] = (64, 48),
    *,
    mode: str = "RGB",
    color: str | tuple[int, ...] = "white",
    marker: str | None = None,
    orientation: int | None = None,
    gps: bool = False,
) -> bytes:
    """產生一張 fmt 格式的圖；marker 在左上角畫一塊色塊，orientation／gps 寫進 EXIF。"""
    image = Image.new(mode, size, color)
    if marker is not None:
        ImageDraw.Draw(image).rectangle((0, 0, size[0] // 4, size[1] // 4), fill=marker)
    exif = Image.Exif()
    if orientation is not None:
        exif[ExifTags.Base.Orientation] = orientation
    if gps:
        exif.get_ifd(ExifTags.IFD.GPSInfo).update(PHOTO_GPS)
    buffer = io.BytesIO()
    image.save(buffer, fmt, exif=exif)
    return buffer.getvalue()


def open_image(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def decompression_bomb_png(width: int = 12_000, height: int = 12_000) -> bytes:
    """檔案只有幾十 KB、解開卻有上億像素的 PNG（全黑的 1-bit 灰階）。

    預設 1.44 億像素：超過 Pillow 的解壓縮炸彈門檻，但還不到它直接拋錯的兩倍，只會警告。
    """
    header = struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)
    row = b"\x00" * (1 + (width + 7) // 8)  # 每列開頭一個 filter byte
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(row * height, 9))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


JPEG = make_image("JPEG")
PNG = make_image("PNG")
WEBP = make_image("WEBP")
# 開頭像 JPEG、其實解不開：通得過魔術位元組檢查，過不了解碼。
MAGIC_ONLY_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def size_of(data: bytes) -> tuple[int, int]:
    return open_image(data).size


# 與 JPEG／PNG 尺寸都不同：假閘道依尺寸回覆，平行辨識時仍分得出是哪一張。
WIDE = make_image("JPEG", (96, 48))
TALL = make_image("PNG", (48, 96))
