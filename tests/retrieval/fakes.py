"""檢索測試用的假 embedding：詞袋雜湊，共用字詞越多相似度越高，不打外部 API。"""

import hashlib
import math
import re

DIM = 64
_TOKEN = re.compile(r"[A-Za-z0-9]+|[一-鿿]")


def embed_text(text: str) -> list[float]:
    vec = [0.0] * DIM
    for token in _TOKEN.findall(text.lower()):
        slot = int(hashlib.md5(token.encode()).hexdigest(), 16) % DIM
        vec[slot] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class BagOfWordsGateway:
    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [embed_text(t) for t in texts]

    def vision(self, prompt, image, mime_type):  # pragma: no cover
        raise NotImplementedError

    def complete(self, prompt, system=None):  # pragma: no cover
        raise NotImplementedError
