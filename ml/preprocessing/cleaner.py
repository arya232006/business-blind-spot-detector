"""Module 2 - preprocessing.

Design rules
* The original text is ALWAYS preserved in ``text_original``.
* ``text_clean`` keeps negations, punctuation that carries sentiment (! ?), casing cues and emojis,
  because VADER / transformers rely on them. We only remove noise (HTML, URLs, control chars, extra spaces).
* ``text_keywords`` (stop-words removed) is a SEPARATE column used only for keyword extraction / labelling.
* Spam / irrelevant filtering and language detection are heuristic and reported, never silent."""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field, asdict

import pandas as pd

from config.logging_config import get_logger
from ml.text_utils import remove_stopwords

log = get_logger(__name__)

_TAG = re.compile(r"<[^>]+>")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_MENTION = re.compile(r"(?<!\w)@\w+")
_HASHTAG = re.compile(r"#(\w+)")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS = re.compile(r"\s+")
_REPEAT_CHARS = re.compile(r"(.)\1{4,}")
_SPAM_PATTERNS = re.compile(
    r"(click here|buy now|free money|work from home|earn \$|crypto giveaway|viagra|casino|100% free|"
    r"limited offer!!!|dm me for|follow (me|back)|subscribe to my|make money fast)", re.I)


@dataclass
class PreprocessReport:
    rows_in: int = 0
    empty_removed: int = 0
    duplicates_removed: int = 0
    spam_removed: int = 0
    too_short_removed: int = 0
    non_english_removed: int = 0
    rows_out: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def clean_text(text: str) -> str:
    """Normalise one string without destroying sentiment-bearing context."""
    if text is None:
        return ""
    s = str(text)
    s = html.unescape(s)
    s = _TAG.sub(" ", s)
    s = unicodedata.normalize("NFKC", s)
    s = _CTRL.sub(" ", s)
    s = _EMAIL.sub(" ", s)
    s = _URL.sub(" ", s)  # URLs carry no sentiment; removed (original kept separately)
    s = _MENTION.sub(" ", s)
    s = _HASHTAG.sub(r"\1", s)  # '#refund' -> 'refund' keeps the word
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = _REPEAT_CHARS.sub(r"\1\1\1", s)  # 'soooooo' -> 'sooo' (VADER still reads the emphasis)
    s = _WS.sub(" ", s).strip()
    return s


def is_spam(text: str) -> bool:
    if _SPAM_PATTERNS.search(text):
        return True
    words = text.lower().split()
    if len(words) >= 6 and len(set(words)) / len(words) < 0.35:  # heavy word repetition
        return True
    letters = sum(c.isalpha() for c in text)
    return len(text) > 12 and letters / max(len(text), 1) < 0.3  # mostly symbols / digits


_EN_FUNCTION_WORDS = frozenset(
    "the a an is are was were be been it its this that these those and or but not no for to of in on at with my "
    "your our their i you we they he she me us them have has had do does did can could will would should just very "
    "so too from by as if when then than there here what which who how why all any more most".split())


def detect_language(text: str) -> str:
    """Conservative language detection -> ISO code, or 'und' when unsure.

    Short social-media style texts fool statistical detectors, so we first check for English
    function words and only report a non-English language when langdetect is highly confident."""
    toks = re.findall(r"[a-zA-Z']+", text.lower())
    if len(toks) < 4:
        return "und"
    if sum(t in _EN_FUNCTION_WORDS for t in toks) / len(toks) >= 0.15:
        return "en"
    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0
        best = detect_langs(text)[0]
        return best.lang if best.prob >= 0.9 else "und"
    except Exception:  # noqa: BLE001
        return "und"


def preprocess(
    df: pd.DataFrame,
    min_words: int = 3,
    filter_spam: bool = True,
    english_only: bool = True,
    remove_stops: bool = True,
) -> tuple[pd.DataFrame, PreprocessReport]:
    """Clean a standardised dataframe (see ml.ingestion). Returns (clean_df, report).

    Output keeps all input columns and adds: text_original, text_clean, text_keywords, language, record_id."""
    rep = PreprocessReport(rows_in=len(df))
    if df is None or len(df) == 0:
        rep.notes.append("Empty dataset.")
        return pd.DataFrame(columns=list(df.columns) if df is not None else []), rep

    out = df.copy().reset_index(drop=True)
    out["text_original"] = out["text"].astype(str)
    out["text_clean"] = out["text_original"].map(clean_text)

    empty = out["text_clean"].str.len() == 0
    rep.empty_removed = int(empty.sum())
    out = out[~empty]

    short = out["text_clean"].str.split().str.len() < min_words
    rep.too_short_removed = int(short.sum())
    out = out[~short]

    if filter_spam:
        spam = out["text_clean"].map(is_spam)
        rep.spam_removed = int(spam.sum())
        out = out[~spam]

    key = out["text_clean"].str.lower().str.replace(r"[^\w\s]", "", regex=True).str.strip()
    dup = key.duplicated(keep="first")
    rep.duplicates_removed = int(dup.sum())
    out = out[~dup]

    out["language"] = out["text_clean"].map(detect_language)
    if english_only:
        foreign = ~out["language"].isin(["en", "und"])
        rep.non_english_removed = int(foreign.sum())
        if rep.non_english_removed:
            rep.notes.append("Non-English records were excluded because the sentiment/embedding models are English-centric.")
        out = out[~foreign]

    out["text_keywords"] = out["text_clean"].map(remove_stopwords) if remove_stops else out["text_clean"]
    out = out.reset_index(drop=True)
    out["record_id"] = range(len(out))
    rep.rows_out = len(out)
    if rep.rows_out == 0:
        rep.notes.append("All records were removed during cleaning.")
    log.info("Preprocess: %s", rep.to_dict())
    return out, rep
