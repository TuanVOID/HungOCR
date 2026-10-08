"""Regression checks for merging the recovered opening identification block."""

from legal_pipeline import merge_opening_block

HEADER = (
    "CHÍNH PHỦ\n"
    "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
    "Số: 137/2016/NĐ-CP\n"
    "Hà Nội, ngày 29 tháng 9 năm 2016"
)


def test_two_column_body_is_not_duplicated():
    # Body text of 137/2016/NĐ-CP page 1 as olmOCR returned it.
    body = (
        "CHÍNH PHỦ                CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
        "Độc lập - Tự do - Hạnh phúc\n\n"
        "Số: 137/2016/NĐ-CP        Hà Nội, ngày 29 tháng 9 năm 2016\n\n"
        "NGHỊ ĐỊNH\n"
    )
    assert merge_opening_block(HEADER, body) == body


def test_markdown_body_is_not_duplicated():
    body = (
        "**CHÍNH PHỦ** | **CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM**\n\n"
        "Số: 137/2016/NĐ-CP | Hà Nội, ngày 29 tháng 9 năm 2016\n"
    )
    assert merge_opening_block(HEADER, body) == body


def test_missing_block_is_prepended():
    body = "NGHỊ ĐỊNH\nBiểu thuế nhập khẩu ưu đãi đặc biệt"
    assert merge_opening_block(HEADER, body) == HEADER + "\n\n" + body


def test_preamble_names_do_not_hide_missing_block():
    # The preamble repeats the authority name; that is not the opening block.
    body = (
        "NGHỊ ĐỊNH\n"
        "Biểu thuế nhập khẩu ưu đãi đặc biệt\n\n"
        "Căn cứ Luật tổ chức Chính phủ ngày 19 tháng 6 năm 2015;\n\n"
        "Chính phủ ban hành Nghị định Biểu thuế nhập khẩu ưu đãi đặc biệt.\n"
    )
    assert merge_opening_block(HEADER, body) == HEADER + "\n\n" + body


def test_preamble_without_title_does_not_hide_missing_block():
    header = "QUỐC HỘI\nCỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nLuật số: 59/2020/QH14"
    body = (
        "Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;\n\n"
        "Quốc hội ban hành Luật Doanh nghiệp.\n"
    )
    assert merge_opening_block(header, body) == header + "\n\n" + body


def test_only_missing_lines_are_prepended():
    body = "CHÍNH PHỦ    CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM\n\nNGHỊ ĐỊNH\n"
    expected = "Số: 137/2016/NĐ-CP\nHà Nội, ngày 29 tháng 9 năm 2016\n\n" + body
    assert merge_opening_block(HEADER, body) == expected


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("PASS", name)
