"""Data collection: CSV / Excel / TXT / manual text / URL -> one standard schema.

Standard columns (every record keeps source, date, category and extra metadata):
    text, source, date, category, customer_id, rating, metadata(dict)

Nothing here bypasses authentication, CAPTCHAs or robots.txt (see ``extract_url``)."""
from __future__ import annotations

import io
import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field, asdict
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import pandas as pd

from config.logging_config import get_logger
from config.settings import settings

log = get_logger(__name__)

STANDARD_COLUMNS = ["text", "source", "date", "category", "customer_id", "rating", "metadata"]
_ALIASES = {
    "text": ["text", "review", "review_text", "comment", "comments", "content", "body", "message", "feedback",
             "description", "post", "complaint", "tweet", "reviewtext", "customer_feedback", "statement"],
    "date": ["date", "created_at", "timestamp", "time", "datetime", "posted", "posted_at", "review_date", "created",
             "published", "published_at"],
    "source": ["source", "platform", "channel", "origin", "site"],
    "category": ["category", "type", "topic", "label", "section", "content_type"],
    "customer_id": ["customer_id", "user_id", "userid", "user", "author", "author_id", "customer", "username",
                    "reviewer", "handle"],
    "rating": ["rating", "stars", "score", "star_rating"],
}


@dataclass
class ValidationReport:
    ok: bool = True
    rows_in: int = 0
    rows_valid: int = 0
    mapping: dict[str, str | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    missing_dates: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class IngestionError(ValueError):
    """Raised with a user-readable message for malformed uploads."""


# --------------------------------------------------------------------------- parsing
def parse_tabular(content: bytes, filename: str) -> pd.DataFrame:
    """Parse CSV / TSV / XLSX / TXT bytes into a raw DataFrame. Raises IngestionError with a clear message."""
    if not content or not content.strip():
        raise IngestionError("The file is empty.")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise IngestionError(f"File is larger than the {settings.max_upload_mb} MB limit.")
    name = (filename or "").lower()
    try:
        if name.endswith((".xlsx", ".xlsm", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        elif name.endswith(".txt"):
            df = _parse_txt(content)
        elif name.endswith((".csv", ".tsv", ".json")) or "." not in name:
            if name.endswith(".json"):
                df = pd.read_json(io.BytesIO(content))
            else:
                df = _read_csv_any_encoding(content, sep="\t" if name.endswith(".tsv") else None)
        else:
            raise IngestionError(f"Unsupported file type: '{filename}'. Use CSV, XLSX or TXT.")
    except IngestionError:
        raise
    except pd.errors.EmptyDataError as exc:
        raise IngestionError("The file contains no data.") from exc
    except pd.errors.ParserError as exc:
        raise IngestionError(f"The file could not be parsed as a table: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("Failed to parse %s", filename)
        raise IngestionError(f"Could not read '{filename}': {exc}") from exc
    if df.empty:
        raise IngestionError("The file has headers but no data rows.")
    return df


def _read_csv_any_encoding(content: bytes, sep: str | None) -> pd.DataFrame:
    last: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(content), sep=sep, engine="python", encoding=enc, on_bad_lines="skip")
        except UnicodeDecodeError as exc:
            last = exc
    raise IngestionError(f"Could not decode file (tried utf-8 and latin-1): {last}")


def _parse_txt(content: bytes) -> pd.DataFrame:
    text = content.decode("utf-8", errors="replace")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) <= 1:  # one record per line
        blocks = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return pd.DataFrame({"text": blocks})


# --------------------------------------------------------------------------- standardisation
def detect_mapping(columns: list[str]) -> dict[str, str | None]:
    lowered = {str(c).strip().lower().replace(" ", "_"): c for c in columns}
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    for std, names in _ALIASES.items():
        hit = next((lowered[n] for n in names if n in lowered and lowered[n] not in used), None)
        mapping[std] = hit
        if hit is not None:
            used.add(hit)
    return mapping


def standardize(
    df: pd.DataFrame,
    kind: str,
    mapping: dict[str, str | None] | None = None,
    default_source: str = "upload",
) -> tuple[pd.DataFrame, ValidationReport]:
    """Map arbitrary columns onto the standard schema and validate. ``kind`` is 'customer' or 'company'."""
    rep = ValidationReport(rows_in=len(df))
    if df is None or df.empty:
        rep.ok = False
        rep.errors.append("No rows to process.")
        return pd.DataFrame(columns=STANDARD_COLUMNS), rep

    mapping = {**detect_mapping(list(df.columns)), **(mapping or {})}
    if not mapping.get("text"):
        # fall back to the object column with the longest average text
        obj_cols = [c for c in df.columns if df[c].dtype == object]
        if obj_cols:
            best = max(obj_cols, key=lambda c: df[c].astype(str).str.len().mean())
            mapping["text"] = best
            rep.warnings.append(f"No obvious text column - using '{best}' (longest average text).")
        else:
            rep.ok = False
            rep.errors.append("Could not find a text column. Rename one column to 'text' or 'review'.")
            return pd.DataFrame(columns=STANDARD_COLUMNS), rep
    rep.mapping = mapping

    out = pd.DataFrame(index=df.index)
    out["text"] = df[mapping["text"]].astype(str).where(df[mapping["text"]].notna(), "")
    out["source"] = df[mapping["source"]].astype(str) if mapping.get("source") else default_source
    out["category"] = df[mapping["category"]].astype(str) if mapping.get("category") else ("review" if kind == "customer" else "marketing")
    out["customer_id"] = df[mapping["customer_id"]].astype(str) if mapping.get("customer_id") else None
    out["rating"] = pd.to_numeric(df[mapping["rating"]], errors="coerce") if mapping.get("rating") else float("nan")

    if mapping.get("date"):
        out["date"] = pd.to_datetime(df[mapping["date"]], errors="coerce", utc=True).dt.tz_localize(None)
        rep.missing_dates = int(out["date"].isna().sum())
        if rep.missing_dates == len(out):
            rep.warnings.append("The date column could not be parsed - trend analysis will be unavailable.")
        elif rep.missing_dates:
            rep.warnings.append(f"{rep.missing_dates} rows have missing/unparseable dates (kept, excluded from trends).")
    else:
        out["date"] = pd.NaT
        rep.missing_dates = len(out)
        rep.warnings.append("No date column found - trend analysis will be unavailable for this dataset.")

    extra_cols = [c for c in df.columns if c not in {v for v in mapping.values() if v}]
    out["metadata"] = df[extra_cols].apply(lambda r: _json_safe(r.to_dict()), axis=1) if extra_cols else [{} for _ in range(len(df))]

    empty = out["text"].str.strip().eq("") | out["text"].str.lower().isin({"nan", "none", "null"})
    if empty.any():
        rep.warnings.append(f"{int(empty.sum())} rows with empty text were dropped.")
    out = out[~empty].reset_index(drop=True)
    rep.rows_valid = len(out)
    if rep.rows_valid == 0:
        rep.ok = False
        rep.errors.append("No usable text rows remain after removing empty entries.")
    elif rep.rows_valid < 10:
        rep.warnings.append("Fewer than 10 records - topic detection and trends will be unreliable.")
    return out[STANDARD_COLUMNS], rep


def _json_safe(d: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for k, v in d.items():
        try:
            json.dumps(v)
            safe[str(k)] = v
        except TypeError:
            safe[str(k)] = str(v)
        if isinstance(v, float) and v != v:
            safe[str(k)] = None
    return safe


def from_manual_text(text: str, kind: str, source: str = "manual_entry", date=None, category: str | None = None):
    """One record per non-empty line (or blank-line separated block)."""
    if not text or not text.strip():
        raise IngestionError("Please enter some text.")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) <= 1:
        blocks = [ln.strip() for ln in text.splitlines() if ln.strip()]
    df = pd.DataFrame({"text": blocks, "source": source})
    if date is not None:
        df["date"] = pd.to_datetime(date)
    if category:
        df["category"] = category
    return standardize(df, kind, default_source=source)


# --------------------------------------------------------------------------- URL extraction
def _is_public_host(host: str) -> bool:
    """Block localhost / private / link-local targets (basic SSRF protection)."""
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except (socket.gaierror, ValueError):
        return False


def extract_url(url: str, kind: str = "company", min_chars: int = 40, max_records: int = 200):
    """Extract visible text blocks from a public web page.

    Politeness/legality: honours robots.txt, uses an identifying User-Agent, never logs in,
    never solves CAPTCHAs and refuses private network addresses."""
    import requests
    from bs4 import BeautifulSoup

    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise IngestionError("That does not look like a valid URL.")
    if not _is_public_host(parsed.hostname or ""):
        raise IngestionError("The host could not be resolved or points to a private/local address.")

    try:
        rp = RobotFileParser()
        rp.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
        rp.read()
        if not rp.can_fetch(settings.user_agent, url):
            raise IngestionError("The site's robots.txt does not allow automated access to this page.")
    except IngestionError:
        raise
    except Exception:  # robots.txt missing/unreachable -> proceed (standard convention)
        log.info("robots.txt not readable for %s; continuing", parsed.netloc)

    try:
        resp = requests.get(url, headers={"User-Agent": settings.user_agent}, timeout=settings.http_timeout)
    except requests.RequestException as exc:
        raise IngestionError(f"Could not fetch the page: {exc}") from exc
    if resp.status_code in (401, 403, 429):
        raise IngestionError(f"The site refused access (HTTP {resp.status_code}). Authentication/anti-bot pages are not bypassed.")
    if resp.status_code >= 400:
        raise IngestionError(f"The page returned HTTP {resp.status_code}.")
    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype and "text" not in ctype:
        raise IngestionError(f"Unsupported content type: {ctype or 'unknown'}.")

    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "svg", "iframe"]):
        tag.decompose()
    blocks: list[tuple[str, str]] = []
    title = soup.title.get_text(strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        blocks.append(("meta_description", meta["content"].strip()))
    for el in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if len(txt) >= min_chars:
            blocks.append((el.name, txt))
    seen, rows = set(), []
    for tag, txt in blocks:
        if txt.lower() in seen:
            continue
        seen.add(txt.lower())
        rows.append({"text": txt, "source": parsed.netloc, "category": "website", "metadata": {"url": url, "tag": tag, "page_title": title}})
        if len(rows) >= max_records:
            break
    if not rows:
        raise IngestionError("No readable text was found on that page (it may be rendered with JavaScript).")
    df = pd.DataFrame(rows)
    df["date"] = pd.Timestamp.today().normalize()
    std, rep = standardize(df.drop(columns=["metadata"]), kind, default_source=parsed.netloc)
    std["metadata"] = [r["metadata"] for r in rows][: len(std)]
    rep.warnings.append("Web page content has no historical dates - the extraction date was used.")
    return std, rep
