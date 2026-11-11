import io

import pandas as pd
import pytest

from ml.ingestion import IngestionError, detect_mapping, from_manual_text, parse_tabular, standardize
from ml.ingestion.loader import _is_public_host, extract_url


def test_csv_parse_and_auto_mapping():
    raw = parse_tabular(b"Review,Posted,Platform,User\nrefund slow,2026-01-02,Twitter,u1\n", "x.csv")
    std, rep = standardize(raw, "customer")
    assert rep.ok and rep.mapping["text"] == "Review" and rep.mapping["date"] == "Posted"
    assert std.loc[0, "source"] == "Twitter" and std.loc[0, "customer_id"] == "u1"
    assert std.loc[0, "date"] == pd.Timestamp("2026-01-02")


def test_excel_and_txt_supported():
    buf = io.BytesIO()
    pd.DataFrame({"text": ["a b c d", "e f g h"]}).to_excel(buf, index=False)
    assert len(parse_tabular(buf.getvalue(), "x.xlsx")) == 2
    assert len(parse_tabular(b"line one here\nline two here\n", "x.txt")) == 2
    assert len(parse_tabular(b"para one\nstill para one\n\npara two", "x.txt")) == 2


def test_empty_and_unsupported_files_give_clear_errors():
    with pytest.raises(IngestionError, match="empty"):
        parse_tabular(b"", "x.csv")
    with pytest.raises(IngestionError, match="Unsupported"):
        parse_tabular(b"abc", "x.pdf")
    with pytest.raises(IngestionError):
        parse_tabular(b"a,b\n", "x.csv")  # headers only


def test_missing_text_column_reported():
    _, rep = standardize(pd.DataFrame({"a": [1, 2], "b": [3, 4]}), "customer")
    assert not rep.ok and "text column" in rep.errors[0]


def test_missing_and_bad_dates_warn_but_keep_rows():
    df = pd.DataFrame({"text": ["one two three", "four five six"], "date": ["2026-01-01", "garbage"]})
    std, rep = standardize(df, "customer")
    assert rep.ok and len(std) == 2 and rep.missing_dates == 1 and any("date" in w for w in rep.warnings)
    std2, rep2 = standardize(pd.DataFrame({"text": ["one two three"]}), "customer")
    assert rep2.missing_dates == 1 and any("trend" in w.lower() for w in rep2.warnings)


def test_empty_text_rows_dropped():
    std, rep = standardize(pd.DataFrame({"text": ["valid text here", "", None, "nan"]}), "customer")
    assert len(std) == 1 and rep.rows_valid == 1


def test_longest_text_column_fallback():
    std, rep = standardize(pd.DataFrame({"id": [1, 2], "words": ["short", "a much longer piece of feedback text"]}), "customer")
    assert rep.mapping["text"] == "words" and any("longest" in w for w in rep.warnings)


def test_manual_text_records_and_blank_error():
    std, rep = from_manual_text("first record here\nsecond record here", "customer")
    assert len(std) == 2
    with pytest.raises(IngestionError):
        from_manual_text("   ", "customer")


def test_detect_mapping_aliases():
    m = detect_mapping(["comment", "created_at", "author", "stars"])
    assert (m["text"], m["date"], m["customer_id"], m["rating"]) == ("comment", "created_at", "author", "stars")


def test_private_hosts_blocked():
    assert not _is_public_host("localhost") and not _is_public_host("127.0.0.1") and not _is_public_host("192.168.1.5")
    with pytest.raises(IngestionError, match="private"):
        extract_url("http://127.0.0.1:8000/admin")
