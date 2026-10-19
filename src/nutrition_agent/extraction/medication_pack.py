"""藥包 VLM：只讀包裝上的藥名原文，不判斷是什麼藥；名稱對照由確定性的藥名表負責。"""

import json

from pydantic import BaseModel, ConfigDict, ValidationError

from nutrition_agent.gateway import ModelGateway
from nutrition_agent.reference.drug_names import normalize_name

MAX_NAMES_PER_PHOTO = 20

PROMPT = """你是藥品包裝的讀字工具。請只回報照片上看得到的藥品名稱原文（商品名、學名或中文名），不要推測、不要補充、不要說明用途、不要判斷是什麼藥。
一張照片可能有多個藥盒或藥袋，每個藥名各列一個。劑量、廠牌、效期、批號都不要列。
輸出一個 JSON 物件，不要有其他文字：
{
  "readable": 照片是否看得清楚藥名（true/false）,
  "names": ["藥名原文", ...]
}
讀不清楚就不要列，不要猜。
"""

UNREADABLE_HINT = "這張照片讀不到藥名，請重拍：對準藥盒或藥袋上的藥名，光線充足、避免反光，字要清晰。"


class MedicationPackReading(BaseModel):
    model_config = ConfigDict(extra="ignore")

    readable: bool
    names: list[str] = []


UNREADABLE = MedicationPackReading(readable=False)


def _json_text(reply: str) -> str:
    start, end = reply.find("{"), reply.rfind("}")
    return reply[start : end + 1] if 0 <= start < end else reply


def _clean_names(names: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for name in names:
        text = name.strip()
        key = normalize_name(text)
        if text and key not in seen:
            seen.add(key)
            cleaned.append(text)
    return cleaned[:MAX_NAMES_PER_PHOTO]


def parse_pack_reading(reply: str) -> MedicationPackReading:
    """解析模型回覆；格式不對、標示讀不到或一個藥名都沒有，都當成這張讀不到。"""
    try:
        raw = MedicationPackReading.model_validate(json.loads(_json_text(reply)))
    except (ValueError, ValidationError):
        return UNREADABLE
    names = _clean_names(raw.names)
    if not raw.readable or not names:
        return UNREADABLE
    return MedicationPackReading(readable=True, names=names)


def read_medication_pack(gateway: ModelGateway, image: bytes, mime_type: str) -> MedicationPackReading:
    return parse_pack_reading(gateway.vision(PROMPT, image, mime_type))
