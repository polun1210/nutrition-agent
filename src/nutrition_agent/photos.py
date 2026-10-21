"""保健食品與藥包照片存在 S3 相容的物件儲存（本機是 SeaweedFS）；歸屬與存取檢查由 API 負責。

object key 是「前綴/隨機 ID.副檔名」，不含任何使用者資訊。只用基本的 S3 操作，
換成 AWS S3 或 R2 只需要改設定。
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
MEDICATION_PREFIX = "medication"
_KEY_PATTERN = re.compile(r"(product|medication)/[0-9a-f]{32}\.(jpg|png|webp)")
_MISSING_CODES = {"NoSuchKey", "404"}  # get_object 回 NoSuchKey；HEAD 沒有 body，只有 "404"
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
    def __init__(self, client: BaseClient, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> "PhotoStore":
        client = make_s3_client(
            settings.s3_internal_endpoint,
            settings.s3_access_key,
            settings.s3_secret_key,
            settings.s3_region,
        )
        return cls(client, settings.s3_bucket)

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

    def read(self, key: str) -> bytes:
        if not _KEY_PATTERN.fullmatch(key):  # 例如本機磁碟時代留下的舊檔名
            raise PhotoNotFound(key)
        with _storage_errors():
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as err:
                if _error_code(err) in _MISSING_CODES:
                    raise PhotoNotFound(key) from err
                raise
            return response["Body"].read()

    def delete(self, key: str) -> None:
        """S3 的刪除本來就冪等：物件不存在也算成功。"""
        if not _KEY_PATTERN.fullmatch(key):
            return
        with _storage_errors():
            self._client.delete_object(Bucket=self._bucket, Key=key)
