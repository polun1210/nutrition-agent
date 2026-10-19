"""藥包 VLM（Seam：read_medication_pack / parse_pack_reading）：只讀字；格式不對一律當讀不到。"""

import json

from nutrition_agent.extraction.medication_pack import parse_pack_reading, read_medication_pack
from tests.fakes import FakeGateway


def reply(names, readable=True):
    return json.dumps({"readable": readable, "names": names}, ensure_ascii=False)


def test_一張照片可以讀出多個藥名():
    reading = parse_pack_reading(reply(["Amlodipine 5mg", "脈優"]))

    assert reading.readable and reading.names == ["Amlodipine 5mg", "脈優"]


def test_回覆前後有多餘文字也能解析():
    reading = parse_pack_reading("好的：\n" + reply(["Zantac"]) + "\n以上")

    assert reading.names == ["Zantac"]


def test_格式錯誤或讀不到名稱都當成讀不到():
    assert not parse_pack_reading("抱歉我看不懂").readable
    assert not parse_pack_reading(reply([])).readable
    assert not parse_pack_reading(reply(["Norvasc"], readable=False)).readable
    assert not parse_pack_reading(reply(["  ", ""])).readable


def test_藥名去空白並在同一張內去重():
    reading = parse_pack_reading(reply([" Norvasc ", "norvasc", "Lipitor"]))

    assert reading.names == ["Norvasc", "Lipitor"]


def test_read_medication_pack_用閘道的視覺回覆():
    gateway = FakeGateway(vision_replies=[reply(["Norvasc"])])

    reading = read_medication_pack(gateway, b"img", "image/jpeg")

    assert reading.names == ["Norvasc"]
    assert gateway.calls[0][0] == "vision"
