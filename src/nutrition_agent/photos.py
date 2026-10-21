"""保健食品與藥包照片存在 S3 相容的物件儲存（本機是 SeaweedFS）；歸屬與存取檢查由 API 負責。

object key 是「前綴/隨機 ID.副檔名」，不含任何使用者資訊。只用基本的 S3 操作，
換成 AWS S3 或 R2 只需要改設定。

讀寫走內部 endpoint；給瀏覽器的 presigned URL 用公開 endpoint 的 client 簽——
SigV4 簽章綁 host，簽完再改 host 會 403。
"""

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from nutrition_agent.config import Settings, resolve_s3_secret_key

MAX_PHOTO_BYTES = 10 * 1024 * 1024
PRODUCT_PREFIX = "product"
MEDICATION_PREFIX = "medication"
_DEFAULT_REGION = "us-east-1"  # 只有這個 region 建 bucket 不能帶 LocationConstraint

# SeaweedFS 沒設網域，只認 path-style；逾時設短，連不上時請求才不會卡住。
_CLIENT_CONFIG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "path"},
    connect_timeout=3,
    read_timeout=10,
)

# 支援的圖片格式：((位移, 魔術位元組), ...) 全部符合才算，加上 MIME 與副檔名。
_SIGNATURES = (
    (((0, b"\xff\xd8\xff"),), "image/jpeg", ".jpg"),
    (((0, b"\x89PNG\r\n\x1a\n"),), "image/png", ".png"),
    (((0, b"RIFF"), (8, b"WEBP")), "image/webp", ".webp"),
)


def _alternatives(options: list[str]) -> str:
    return "|".join(re.escape(option) for option in options)


# save() 產生的 key：「前綴/32 位十六進位.副檔名」，前綴與副檔名都由上面的常數推導。
_KEY_PATTERN = re.compile(
    rf"({_alternatives([PRODUCT_PREFIX, MEDICATION_PREFIX])})/[0-9a-f]{{32}}"
    rf"({_alternatives([ext for *_, ext in _SIGNATURES])})"
)


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """依檔案內容（不信任上傳的檔名或 Content-Type）回傳 (mime, 副檔名)；不支援的格式回 None。"""
    for parts, mime, ext in _SIGNATURES:
        if all(data[offset : offset + len(magic)] == magic for offset, magic in parts):
            return mime, ext
    return None


class PhotoNotFound(Exception):
    """物件不存在（或 key 不是本模組產生的格式）。"""


class PhotoStorageError(Exception):
    """物件儲存連不上或回錯；細節在 __cause__，對外只說稍後再試。"""


@contextmanager
def _storage_errors() -> Iterator[None]:
    try:
        yield
    except (ClientError, BotoCoreError) as err:
        raise PhotoStorageError(str(err)) from err


def _error_code(err: ClientError) -> str:
    return str(err.response.get("Error", {}).get("Code", ""))


def make_s3_client(settings: Settings, endpoint: str) -> BaseClient:
    """金鑰與 region 取自設定；endpoint 另給，因為讀寫與簽 presigned URL 用不同的網址。"""
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=resolve_s3_secret_key(settings),
        config=_CLIENT_CONFIG.merge(
            Config(retries={"max_attempts": settings.s3_max_attempts, "mode": "standard"})
        ),
    )


class PhotoStore:
    def __init__(
        self, client: BaseClient, bucket: str, public_client: BaseClient, url_ttl_seconds: int
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._public_client = public_client
        self._url_ttl_seconds = url_ttl_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "PhotoStore":
        return cls(
            make_s3_client(settings, settings.s3_internal_endpoint),
            settings.s3_bucket,
            make_s3_client(settings, settings.s3_public_endpoint),
            settings.photo_url_ttl_seconds,
        )

    def ensure_bucket(self) -> None:
        """bucket 不存在就建立；已存在（含同時啟動的競態）不算錯。"""
        with _storage_errors():
            try:
                self._client.head_bucket(Bucket=self._bucket)
                return
            except ClientError as err:
                if _error_code(err) not in {"404", "NoSuchBucket"}:
                    raise
            try:
                self._client.create_bucket(**self._create_bucket_args())
            except ClientError as err:
                if _error_code(err) != "BucketAlreadyOwnedByYou":
                    raise

    def _create_bucket_args(self) -> dict:
        region = self._client.meta.region_name
        if region == _DEFAULT_REGION:
            return {"Bucket": self._bucket}
        return {
            "Bucket": self._bucket,
            "CreateBucketConfiguration": {"LocationConstraint": region},
        }

    def save(
        self, data: bytes, ext: str, content_type: str, prefix: str = PRODUCT_PREFIX
    ) -> str:
        """存入並回傳 object key；prefix 區分保健食品與藥包照片。"""
        key = f"{prefix}/{uuid.uuid4().hex}{ext}"
        with _storage_errors():
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
            )
        return key

    def presigned_url(self, key: str) -> str:
        """瀏覽器直接取圖用的短效 GET 網址；只在本機計算簽章，不連物件儲存。"""
        if not _KEY_PATTERN.fullmatch(key):
            raise PhotoNotFound(key)
        with _storage_errors():
            return self._public_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=self._url_ttl_seconds,
            )

    def delete(self, key: str) -> None:
        """S3 的刪除本來就冪等：物件不存在也算成功；key 不是本模組產生的格式就拋 ValueError。"""
        if not _KEY_PATTERN.fullmatch(key):
            raise ValueError(f"不是照片的 object key：{key!r}")
        with _storage_errors():
            self._client.delete_object(Bucket=self._bucket, Key=key)
