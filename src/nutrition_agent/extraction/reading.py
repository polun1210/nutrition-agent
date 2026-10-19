"""VLM 讀標示：只讀字，不猜；回覆解析失敗一律視為整張讀不到。"""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from nutrition_agent.gateway import ModelGateway

Section = Literal["nutrition_table", "ingredient_list", "per_unit_note"]

PROMPT = """你是保健食品標示的讀字工具。請只回報照片上看得到的文字，不要推測、不要補充、不要判斷成分是否安全。
輸出一個 JSON 物件，不要有其他文字：
{
  "readable": 照片是否看得清楚標示（true/false），
  "product_name": 包裝上印的品名，看不到就是 null,
  "serving_size": 「每份」是幾個劑型單位（數字），看不到就是 null,
  "dose_unit": 劑型單位，只能是 "粒"、"錠"、"包"、"匙"、"毫升" 其中之一，看不到就是 null,
  "rows": [
    {
      "raw_name": 成分原文名稱（照抄）,
      "section": "nutrition_table"（營養標示表）、"per_unit_note"（每粒/每錠含量的備註）、"ingredient_list"（成分欄）之一,
      "amount": 每份含量（數字），看不到就是 null,
      "unit": 單位，使用 mg、ug、g、IU、mg_alpha_te（毫克 α-TE）、mg_ne（毫克 NE）、ug_dfe（微克 DFE）、kcal；看不到就是 null,
      "readable": 這一列的字是否讀得清楚（true/false）
    }
  ]
}
規則：同一列有多種單位並列時（例如微克與 IU），只取第一個數字與單位；讀不清楚的欄位填 null，不要猜。
"""

UNREADABLE_HINT = "這張照片看不清楚標示，請重拍：對準成分欄與營養標示，光線充足、避免反光，字要清晰、整張都在畫面內。"


class VlmRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw_name: str
    section: Section = "nutrition_table"
    amount: float | None = None
    unit: str | None = None
    readable: bool = True


class VlmReading(BaseModel):
    model_config = ConfigDict(extra="ignore")

    readable: bool
    product_name: str | None = None
    serving_size: float | None = None
    dose_unit: str | None = None
    rows: list[VlmRow] = []


UNREADABLE = VlmReading(readable=False)


def _json_text(reply: str) -> str:
    start, end = reply.find("{"), reply.rfind("}")
    return reply[start : end + 1] if 0 <= start < end else reply


def parse_reading(reply: str) -> VlmReading:
    """解析模型回覆；格式不對就當成整張讀不到，不嘗試修補。"""
    try:
        return VlmReading.model_validate(json.loads(_json_text(reply)))
    except (ValueError, ValidationError):
        return UNREADABLE


def read_label(gateway: ModelGateway, image: bytes, mime_type: str) -> VlmReading:
    return parse_reading(gateway.vision(PROMPT, image, mime_type))
