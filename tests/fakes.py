"""可注入的假模型閘道：tests/ 不打外部 API。"""

from dataclasses import dataclass, field


@dataclass
class FakeGateway:
    vision_reply: str = "fake-vision"
    complete_reply: str = "fake-completion"
    embedding_dim: int = 4
    calls: list[tuple[str, object]] = field(default_factory=list)

    def vision(self, prompt: str, image: bytes, mime_type: str) -> str:
        self.calls.append(("vision", prompt))
        return self.vision_reply

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append(("complete", prompt))
        return self.complete_reply

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(("embed", texts))
        return [[0.0] * self.embedding_dim for _ in texts]
