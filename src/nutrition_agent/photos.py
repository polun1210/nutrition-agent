"""保健食品照片存在 S3 相容的物件儲存（本機是 SeaweedFS）；歸屬與存取檢查由 API 負責。

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

from nutrition_agent.config import Settings

MAX_PHOTO_BYTES = 10 * 1024 * 1024
PRODUCT_PREFIX = "product"
_KEY_PATTERN = re.compile(r"product/[0-9a-f]{32}\.(jpg|png|webp)")
_DEFAULT_REGION = "us-east-1"  # 只有這個 region 建 bucket 不能帶 LocationConstraint

# SeaweedFS 沒設網域，只認 path-style；連線失敗時少重試、早點放棄，請求才不會卡住。
_CLIENT_CONFIG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "path"},
    retries={"max_attempts": 2, "mode": "standard"},
    connect_timeout=3,
    read_timeout=10,
)

_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
)


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """依檔案內容（不信任上傳的檔名或 Content-Type）回傳 (mime, 副檔名)；不支援的格式回 None。"""
    for magic, mime, ext in _SIGNATURES:
        if data.startswith(magic):
            return mime, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
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


def make_s3_client(endpoint: str, access_key: str, secret_key: str, region: str) -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=_CLIENT_CONFIG,
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
        def client(endpoint: str) -> BaseClient:
            return make_s3_client(
                endpoint, settings.s3_access_key, settings.s3_secret_key, settings.s3_region
            )

        return cls(
            client(settings.s3_internal_endpoint),
            settings.s3_bucket,
            client(settings.s3_public_endpoint),
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

    def save(self, data: bytes, ext: str, content_type: str) -> str:
        """存入並回傳 object key。"""
        key = f"{PRODUCT_PREFIX}/{uuid.uuid4().hex}{ext}"
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
        """S3 的刪除本來就冪等：物件不存在也算成功。"""
        if not _KEY_PATTERN.fullmatch(key):
            return
        with _storage_errors():
            self._client.delete_object(Bucket=self._bucket, Key=key)
