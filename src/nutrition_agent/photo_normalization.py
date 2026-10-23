"""照片正規化：上傳的照片在辨識與存檔之前統一成同一種 JPEG（見 ADR-0007）。

純函數、不碰網路與資料庫：正式的上傳端點與 VLM eval 共用，eval 量到的就是使用者實際得到的。
"""

import io

from PIL import Image, ImageOps

NORMALIZED_MIME = "image/jpeg"
NORMALIZED_EXT = ".jpg"
JPEG_QUALITY = 85
# 長邊上限：標示上的小字仍讀得清楚，檔案與 VLM 的影像 token 都小很多。
MAX_LONG_SIDE = 1600
# 解壓縮炸彈防護：Pillow 超過這個像素數只發警告、到兩倍才拋錯，這裡一超過就拒絕，
# 不讓幾十 KB 的檔案在記憶體裡解成上億像素。手機照片（5000 萬像素以下）遠低於此。
MAX_PIXELS = Image.MAX_IMAGE_PIXELS
# 只解這三種：魔術位元組檢查已經擋掉其他格式，這裡再限制一次 Pillow 會嘗試的解碼器。
_FORMATS = ("JPEG", "PNG", "WEBP")


class UnreadablePhoto(ValueError):
    """照片解不開或像素數超過上限；細節在 __cause__，對外只請使用者重拍或換一張。"""


def normalize_photo(data: bytes) -> bytes:
    """解碼 → 依 EXIF 方向轉正 → 長邊縮到 MAX_LONG_SIDE → 轉 RGB（透明補白）→ 重新編碼成 JPEG。

    存檔時不帶任何中繼資料（EXIF、GPS、ICC、XMP、註解）。解不開就拋 UnreadablePhoto。
    """
    image = _to_rgb(_shrink(ImageOps.exif_transpose(_decode(data))))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def _shrink(image: Image.Image) -> Image.Image:
    """長邊超過 MAX_LONG_SIDE 時等比例縮小；小圖不放大。"""
    scale = MAX_LONG_SIDE / max(image.size)
    if scale >= 1:
        return image
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def _to_rgb(image: Image.Image) -> Image.Image:
    """JPEG 沒有透明度：透明的部分疊在白底上，否則轉 RGB 時會變成黑的。"""
    if not image.has_transparency_data:
        return image.convert("RGB")
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, "white")
    return Image.alpha_composite(background, rgba).convert("RGB")


def _decode(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data), formats=_FORMATS)  # 只讀檔頭，還沒解像素
    except Exception as err:  # 不信任的檔案：Pillow 的各種解析錯誤都當成解不開
        raise UnreadablePhoto(str(err)) from err
    if image.width * image.height > MAX_PIXELS:
        raise UnreadablePhoto(f"像素數超過上限：{image.width}×{image.height}")
    try:
        image.load()
    except Exception as err:
        raise UnreadablePhoto(str(err)) from err
    return image
