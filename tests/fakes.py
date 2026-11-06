"""可注入的假模型閘道：tests/ 不打外部 API。"""

import io
import threading
from dataclasses import dataclass, field

from PIL import Image

from nutrition_agent.structured import ResponseSchema

Reply = str | Exception


@dataclass
class FakeGateway:
    vision_reply: str = "fake-vision"
    # 依呼叫順序逐次回覆（用完後退回 vision_reply）；元素為例外時會丟出來，模擬模型服務故障。
    # 平行辨識時呼叫順序不固定，一次多張照片請改用 vision_by_size。
    vision_replies: list[Reply] = field(default_factory=list)
    # 依送入圖片的 (寬, 高) 決定回覆，優先於 vision_replies：平行執行時仍能對上是哪一張。
    vision_by_size: dict[tuple[int, int], Reply] = field(default_factory=dict)
    complete_reply: str = "fake-completion"
    embedding_dim: int = 4
    calls: list[tuple[str, object]] = field(default_factory=list)
    # 送進 vision 的 (圖檔, MIME)，依呼叫順序：驗證模型看到的就是存下來的那一張。
    images: list[tuple[bytes, str]] = field(default_factory=list)
    # 每次 vision／complete 收到的 schema（沒傳就是 None），依呼叫順序。
    schemas: list[ResponseSchema | None] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def vision(
        self, prompt: str, image: bytes, mime_type: str, *, schema: ResponseSchema | None = None
    ) -> str:
        with self._lock:
            self.calls.append(("vision", prompt))
            self.schemas.append(schema)
            self.images.append((image, mime_type))
            reply = self._next_vision_reply(image)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def _next_vision_reply(self, image: bytes) -> Reply:
        if self.vision_by_size:
            return self.vision_by_size[Image.open(io.BytesIO(image)).size]
        if self.vision_replies:
            return self.vision_replies.pop(0)
        return self.vision_reply

    def complete(
        self, prompt: str, system: str | None = None, *, schema: ResponseSchema | None = None
    ) -> str:
        with self._lock:
            self.calls.append(("complete", prompt))
            self.schemas.append(schema)
        return self.complete_reply

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            self.calls.append(("embed", texts))
        return [[0.0] * self.embedding_dim for _ in texts]
