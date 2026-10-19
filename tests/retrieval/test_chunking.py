from nutrition_agent.retrieval.chunking import chunk_markdown, strip_base64_images

B64 = "data:image/png;base64," + "A" * 500


def test_strip_base64_images_removes_inline_image_data():
    text = "前文\n![圖](" + B64 + ")\n後文"
    cleaned = strip_base64_images(text)
    assert "base64" not in cleaned
    assert "前文" in cleaned and "後文" in cleaned


def test_chunks_follow_headings_and_keep_section_path():
    text = "# Calcium\n\n## Introduction\n\n簡介內容。\n\n## Interactions with Medications\n\n### Levothyroxine\n\n間隔四小時。\n"
    chunks = chunk_markdown(text)
    sections = {c.section: c.text for c in chunks}
    assert "Interactions with Medications > Levothyroxine" in sections
    assert "間隔四小時。" in sections["Interactions with Medications > Levothyroxine"]
    assert "簡介內容。" in sections["Introduction"]


def test_chunk_text_is_verbatim_and_locatable_in_original():
    text = "## A\n\n第一段。\n\n第二段。\n\n## B\n\n乙內容。\n"
    for chunk in chunk_markdown(text):
        assert text[chunk.start : chunk.end] == chunk.text


def test_long_section_is_split_without_losing_text():
    paragraphs = [f"段落{i}。" + "字" * 300 for i in range(20)]
    text = "## Long\n\n" + "\n\n".join(paragraphs) + "\n"
    chunks = chunk_markdown(text, max_chars=1000)
    assert len(chunks) > 1
    assert all(len(c.text) <= 1000 for c in chunks)
    assert all(c.section == "Long" for c in chunks)
    joined = "".join(c.text for c in chunks)
    for p in paragraphs:
        assert p in joined


def test_tfda_bracket_headings_are_sections():
    text = "【適應症】\n高血壓。\n\n【交互作用】\n與鉀鹽併用須謹慎。\n"
    sections = {c.section: c.text for c in chunk_markdown(text)}
    assert "交互作用" in sections
    assert "鉀鹽" in sections["交互作用"]


def test_text_before_first_heading_is_kept():
    chunks = chunk_markdown("前言文字。\n\n## A\n\n內容。\n")
    assert any("前言文字。" in c.text for c in chunks)
