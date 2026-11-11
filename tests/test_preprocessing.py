import pandas as pd

from ml.preprocessing import clean_text, detect_language, is_spam, preprocess


def test_html_and_urls_removed_original_kept():
    df = pd.DataFrame({"text": ["<p>Refund is <b>slow</b>! See https://example.com/x now</p>"]})
    out, _ = preprocess(df)
    assert "<" not in out.loc[0, "text_clean"] and "http" not in out.loc[0, "text_clean"]
    assert out.loc[0, "text_original"].startswith("<p>")


def test_negation_and_emoji_and_exclamation_preserved():
    cleaned = clean_text("This is NOT good 😡!!  Never again.")
    assert "NOT" in cleaned and "😡" in cleaned and "!" in cleaned and "Never" in cleaned
    assert "  " not in cleaned


def test_whitespace_and_elongation_normalised():
    assert clean_text("sooooooo    slow") == "sooo slow"


def test_hashtag_keeps_word_mentions_removed():
    assert clean_text("@brand #refund please") == "refund please"


def test_duplicates_empty_spam_short_removed():
    df = pd.DataFrame({"text": ["Refund took too long today", "refund took too long today!", "", "   ", "ok", "CLICK HERE buy now free money!!!",
                                "Support never replied to my ticket"]})
    out, rep = preprocess(df)
    assert rep.duplicates_removed == 1 and rep.empty_removed == 2 and rep.spam_removed == 1 and rep.too_short_removed == 1
    assert len(out) == 2 and "record_id" in out


def test_spam_heuristics():
    assert is_spam("buy now!!! click here")
    assert is_spam("aaa bbb aaa bbb aaa bbb aaa bbb")
    assert not is_spam("The delivery was late and the box was damaged.")


def test_language_detection_conservative():
    assert detect_language("Refund is taking so long") == "en"
    assert detect_language("ok") == "und"
    assert detect_language("Der Kundenservice ist wirklich sehr schlecht und das Team antwortet nie auf meine Anfragen") == "de"


def test_non_english_filtered_but_reported():
    df = pd.DataFrame({"text": ["Der Kundenservice ist wirklich sehr schlecht und das Team antwortet nie auf meine Anfragen",
                                "The customer service is really bad and nobody answers"]})
    out, rep = preprocess(df)
    assert rep.non_english_removed == 1 and len(out) == 1


def test_empty_frame_does_not_crash():
    out, rep = preprocess(pd.DataFrame({"text": []}))
    assert len(out) == 0 and rep.rows_in == 0


def test_keyword_column_drops_stopwords_but_keeps_negation():
    out, _ = preprocess(pd.DataFrame({"text": ["The refund is not working for me at all"]}))
    kw = out.loc[0, "text_keywords"].lower().split()
    assert "not" in kw and "the" not in kw
