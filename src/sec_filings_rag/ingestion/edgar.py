"""Fetch 10-K filings from SEC EDGAR.

SEC fair-access rules require a descriptive User-Agent with contact info and ask clients to stay
under ~10 requests/second. We resolve ticker -> CIK -> latest 10-K primary document and download
the raw HTML. See https://www.sec.gov/os/accessing-edgar-data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from sec_filings_rag.config import get_settings

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc}"

# Be a polite EDGAR citizen: small floor between requests.
_MIN_REQUEST_INTERVAL = 0.15
_last_request_at = 0.0


@dataclass(frozen=True)
class Filing:
    ticker: str
    company: str
    cik: int
    form: str
    fiscal_year: str  # filing/report date's year (YYYY)
    accession: str
    primary_doc: str
    url: str


def _client() -> httpx.Client:
    ua = get_settings().sec_user_agent
    return httpx.Client(
        headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"},
        timeout=30.0,
        follow_redirects=True,
    )


def _throttle() -> None:
    global _last_request_at
    delta = time.monotonic() - _last_request_at
    if delta < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - delta)
    _last_request_at = time.monotonic()


def _get(client: httpx.Client, url: str) -> httpx.Response:
    _throttle()
    resp = client.get(url)
    resp.raise_for_status()
    return resp


def resolve_cik(client: httpx.Client, ticker: str) -> tuple[int, str]:
    """Map a ticker symbol to its zero-padded CIK and company name."""
    data = _get(client, _TICKERS_URL).json()
    ticker = ticker.upper()
    for row in data.values():
        if row["ticker"].upper() == ticker:
            return int(row["cik_str"]), row["title"]
    raise ValueError(f"ticker {ticker!r} not found in EDGAR company_tickers.json")


def latest_filing(client: httpx.Client, ticker: str, form: str = "10-K") -> Filing:
    """Locate the most recent filing of `form` for `ticker`."""
    cik, company = resolve_cik(client, ticker)
    cik10 = f"{cik:010d}"
    subs = _get(client, _SUBMISSIONS_URL.format(cik10=cik10)).json()
    recent = subs["filings"]["recent"]
    for i, f in enumerate(recent["form"]):
        if f == form:
            accession = recent["accessionNumber"][i]
            primary_doc = recent["primaryDocument"][i]
            report_date = recent["reportDate"][i] or recent["filingDate"][i]
            accession_nodash = accession.replace("-", "")
            url = _ARCHIVE_URL.format(cik=cik, accession_nodash=accession_nodash, doc=primary_doc)
            return Filing(
                ticker=ticker.upper(),
                company=company,
                cik=cik,
                form=form,
                fiscal_year=report_date[:4],
                accession=accession,
                primary_doc=primary_doc,
                url=url,
            )
    raise ValueError(f"no {form} found for {ticker!r}")


def download_filing(client: httpx.Client, filing: Filing, dest_dir: Path) -> Path:
    """Download the primary document HTML to `dest_dir`, returning the local path (cached)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{filing.ticker}_{filing.form}_{filing.fiscal_year}.html"
    if out.exists():
        return out
    html = _get(client, filing.url).text
    out.write_text(html, encoding="utf-8")
    return out


def fetch(ticker: str, form: str = "10-K", dest_dir: Path | None = None) -> tuple[Filing, Path]:
    """Convenience: resolve + download the latest `form` for `ticker`."""
    dest = dest_dir or Path(get_settings().filings_dir)
    with _client() as client:
        filing = latest_filing(client, ticker, form)
        path = download_filing(client, filing, dest)
    return filing, path
