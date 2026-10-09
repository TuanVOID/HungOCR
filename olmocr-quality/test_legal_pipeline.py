"""Regression checks for the opening-block merge and identifier-column recovery."""

from legal_pipeline import merge_opening_block, missing_ids, split_merged_ids

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


HEAD = (
    "<table>\n  <tr>\n    <th>Mã hàng</th>\n    <th>Tên gọi, mô tả hàng hóa</th>\n"
    '    <th colspan="3">Thuế suất VN-EAEU FTA (%)</th>\n  </tr>\n'
    "  <tr>\n    <th></th>\n    <th></th>\n    <th>2016</th>\n    <th>2017</th>\n"
    "    <th>2018</th>\n  </tr>\n"
)


def _row(code, text, rates=("0", "0", "0")):
    cells = "".join(f"\n    <td>{v}</td>" for v in (code, text, *rates))
    return f"  <tr>{cells}\n  </tr>\n"


ROWS = [
    ("0101.21.00", "- - Loại thuần chủng để nhân giống"),
    ("0101.29.00", "- - Loại khác"),
    ("0101.30.10", "- - Loại thuần chủng để nhân giống"),
    ("0101.30.90", "- - Loại khác"),
]


def _table(first_header, rows):
    head = f"<table>\n  <tr>\n    <th>{first_header}</th>\n    <th>Nội dung</th>\n"
    head += "    <th>Ghi chú</th>\n  </tr>\n"
    return head + "".join(_row(i, t, ("x",)) for i, t in rows) + "</table>"


def test_codes_merged_into_description_move_back():
    # Page 5 of 137/2016/NĐ-CP: the model wrote "0101.21.00 - Loại ..." in the
    # description cell and left the code cell empty.
    merged = HEAD + "".join(_row("", f"{c} {t}") for c, t in ROWS) + "</table>"
    fixed = HEAD + "".join(_row(c, t) for c, t in ROWS) + "</table>"
    assert split_merged_ids(merged) == fixed
    assert not missing_ids(fixed)


def test_dropped_code_column_is_detected():
    dropped = HEAD + "".join(_row("", t) for _, t in ROWS) + "</table>"
    assert split_merged_ids(dropped) == dropped
    assert missing_ids(dropped)


def test_other_identifier_kinds_move_back():
    cases = [
        ("STT", ["1", "2", "3", "4"]),
        ("TT", ["I.", "II.", "III.", "IV."]),
        ("Số thứ tự", ["a)", "b)", "c)", "d)"]),
        ("Ký hiệu", ["QHHH-01", "QHHH-02", "KTX-01", "KTX-02"]),
        ("Số hiệu", ["137/2016/NĐ-CP", "57/2020/NĐ-CP", "18/2021/TT-BTC", "9/2019/QĐ-TTg"]),
    ]
    for header, ids in cases:
        texts = [f"Nội dung dòng {n}" for n in range(len(ids))]
        merged = _table(header, [("", f"{i} {t}") for i, t in zip(ids, texts)])
        assert split_merged_ids(merged) == _table(header, list(zip(ids, texts))), header


def test_isolated_number_in_text_is_not_moved():
    rows = [("1", "Hạng mục A"), ("", "2 phòng ngủ, 1 phòng khách"), ("2", "Hạng mục B")]
    table = _table("STT", rows)
    assert split_merged_ids(table) == table


def test_sparse_sub_rows_are_left_alone():
    rows = [("1", "Hạng mục A"), ("", "- chi tiết 1"), ("", "- chi tiết 2"),
            ("2", "Hạng mục B"), ("", "- chi tiết 3")]
    table = _table("STT", rows)
    assert split_merged_ids(table) == table
    assert not missing_ids(table)


def test_non_identifier_columns_are_untouched():
    for header in ("Hạng mục", "Số lượng", "Nội dung"):
        merged = _table(header, [("", f"{n} đơn vị loại {n}") for n in range(1, 6)])
        assert split_merged_ids(merged) == merged, header
        assert not missing_ids(merged), header


def test_group_rows_without_values_are_not_counted():
    table = HEAD + "".join(_row("", f"Nhóm {i}", ("", "", "")) for i in range(6))
    assert not missing_ids(table + "</table>")


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("PASS", name)
