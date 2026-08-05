from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

_ETFSBR_BASE = "https://www.etfsbrasil.com.br/etfs"
_SERIES_RE = re.compile(r'series\\":\\"\$([0-9a-f]+)')
_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', re.S)
_ROW_HEADER_RE = re.compile(r"^[0-9a-f]+:[A-Za-z]")
_INLINE_SERIES_END_MARKERS = (
    '\\",\\"customAxis',
    '\\",\\"usePercentageComparison',
    '\\",\\"isPercentage',
    '\\",\\"color',
    '\\",\\"name',
)


class EtfBrFetchError(Exception):
    pass


@dataclass
class EtfBrData:
    ticker: str
    nome: str | None
    cotacao: float
    pl_cota: float
    premio_desconto_pct: float
    low_52: float
    high_52: float
    pl_total_mm: float | None
    taxa_adm_pct: float | None
    cotistas: int | None
    cnpj: str | None
    indice: str | None


def fetch_etf_br(ticker: str) -> EtfBrData:
    url = f"{_ETFSBR_BASE}/{ticker.lower()}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise EtfBrFetchError(str(exc)) from exc
    if resp.status_code != 200:
        raise EtfBrFetchError(f"HTTP {resp.status_code}")
    return _parse_etfsbrasil_html(ticker.upper(), resp.text)


def _parse_etfsbrasil_html(ticker: str, html: str) -> EtfBrData:
    soup = BeautifulSoup(html, "html.parser")
    cotacao = _parse_cotacao(soup)
    if cotacao is None:
        raise EtfBrFetchError("cotação ausente")

    pushes = _PUSH_RE.findall(html)
    if not pushes:
        raise EtfBrFetchError("payload RSC ausente")

    spread_blob = _get_series_blob(pushes, lambda push: "Spread entre o Pre" in push)
    quot_blob = _get_series_blob(
        pushes,
        lambda push: 'eyebrow\\",\\"children\\":\\"Performance' in push,
    )
    if not spread_blob or not quot_blob:
        raise EtfBrFetchError("gráficos spread/cotação ausentes")

    spread_pct = _parse_latest_spread(spread_blob)
    if spread_pct is None:
        raise EtfBrFetchError("spread ausente")

    low_52, high_52 = _parse_quotation_52w(quot_blob, cotacao)
    if low_52 is None or high_52 is None:
        raise EtfBrFetchError("histórico 52w ausente")

    pl_cota = cotacao / (1 + spread_pct / 100)
    premio_desconto_pct = (cotacao / pl_cota - 1) * 100

    return EtfBrData(
        ticker=ticker,
        nome=_parse_nome(soup),
        cotacao=cotacao,
        pl_cota=pl_cota,
        premio_desconto_pct=premio_desconto_pct,
        low_52=low_52,
        high_52=high_52,
        pl_total_mm=_parse_highlight(soup, "Patrimônio líquido (R$ MM)"),
        taxa_adm_pct=_parse_highlight(soup, "Taxa de administração total")
        or _parse_fact(soup, "Taxa de administração primária"),
        cotistas=_parse_cotistas(soup),
        cnpj=_parse_fact(soup, "CNPJ"),
        indice=_parse_fact(soup, "Índice"),
    )


def _parse_brl_number(value: str | None) -> float | None:
    if value is None:
        return None
    s = str(value).strip().replace("R$", "").replace("%", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_cotacao(soup: BeautifulSoup) -> float | None:
    el = soup.select_one('[class*="quoteValue"]')
    if el is None:
        return None
    return _parse_brl_number(el.get_text(" ", strip=True))


def _parse_nome(soup: BeautifulSoup) -> str | None:
    h1 = soup.find("h1")
    if h1 is None:
        return None
    p = h1.find_parent("div", class_=lambda c: c and "title" in c)
    if p is not None:
        name_el = p.select_one('[class*="__name"]')
        if name_el is not None:
            return name_el.get_text(" ", strip=True) or None
    return h1.get_text(" ", strip=True) or None


def _parse_highlight(soup: BeautifulSoup, label: str) -> float | None:
    for field in soup.select('[class*="highlightField"]'):
        lab = field.select_one('[class*="label"]')
        val = field.select_one('[class*="value"]')
        if lab and val and lab.get_text(strip=True) == label:
            return _parse_brl_number(val.get_text(" ", strip=True))
    return None


def _parse_fact(soup: BeautifulSoup, label: str) -> str | None:
    for field in soup.select('[class*="information-field"]'):
        lab = field.select_one('[class*="label"]')
        if lab is None or lab.get_text(strip=True) != label:
            continue
        text = field.get_text(" ", strip=True)
        return text.replace(label, "", 1).strip() or None
    return None


def _parse_cotistas(soup: BeautifulSoup) -> int | None:
    for field in soup.select('[class*="highlightField"]'):
        lab = field.select_one('[class*="label"]')
        val = field.select_one('[class*="value"]')
        if lab and val and lab.get_text(strip=True) == "Número de cotistas":
            digits = re.sub(r"\D", "", val.get_text(" ", strip=True))
            if not digits:
                return None
            try:
                return int(digits)
            except ValueError:
                return None
    return None


def _decode_push(raw: str) -> str:
    return json.loads(
        '"'
        + raw.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
        + '"'
    )


def _find_series_chunk_id(pushes: list[str], marker: str) -> str | None:
    for push in pushes:
        if marker in push:
            match = _SERIES_RE.search(push)
            if match:
                return match.group(1)
    return None


def _find_performance_series_chunk_id(pushes: list[str]) -> str | None:
    for push in pushes:
        if 'eyebrow\\",\\"children\\":\\"Performance' in push:
            match = _SERIES_RE.search(push)
            if match:
                return match.group(1)
    return None


def _get_series_blob(pushes: list[str], marker_fn) -> bytes:
    for push in pushes:
        if not marker_fn(push):
            continue
        match = _SERIES_RE.search(push)
        if match:
            blob = _concat_t_chunk(pushes, match.group(1))
            if blob:
                return blob
        inline = _extract_inline_series(push)
        if inline:
            return inline
    return b""


def _extract_inline_series(push: str) -> bytes | None:
    key = 'series\\":\\"'
    pos = push.find(key)
    if pos < 0:
        return None
    start = pos + len(key)
    if start < len(push) and push[start] == "$":
        return None
    for end_marker in _INLINE_SERIES_END_MARKERS:
        end = push.find(end_marker, start)
        if end >= 0:
            series_esc = push[start:end]
            return bytes(ord(c) & 0xFF for c in _decode_push(series_esc))
    return None


def _concat_t_chunk(pushes: list[str], chunk_id: str) -> bytes:
    header = f"{chunk_id}:T"
    start = next(
        (
            i
            for i, p in enumerate(pushes)
            if p.startswith(header) or p.rfind(header) >= 0 and p[p.rfind(header) :].startswith(header)
        ),
        None,
    )
    if start is None:
        return b""
    parts: list[bytes] = []
    j = start + 1
    while j < len(pushes):
        push = pushes[j]
        if _ROW_HEADER_RE.match(push):
            break
        parts.append(bytes(ord(c) & 0xFF for c in _decode_push(push)))
        j += 1
    return b"".join(parts)


def _parse_latest_spread(blob: bytes) -> float | None:
    for i in range(len(blob) - 4, -1, -1):
        value = struct.unpack_from("<f", blob, i)[0]
        if 0.001 < abs(value) < 3:
            return value
    return None


def _parse_quotation_52w(blob: bytes, cotacao: float) -> tuple[float | None, float | None]:
    for lo_mult, hi_mult in ((0.77, 1.11), (0.6, 1.4), (0.5, 1.5), (0.4, 1.6), (0.3, 2.0)):
        lo = cotacao * lo_mult
        hi = cotacao * hi_mult
        prices = [
            struct.unpack_from("<f", blob, i)[0]
            for i in range(len(blob) - 4)
            if lo <= struct.unpack_from("<f", blob, i)[0] <= hi
        ]
        if len(prices) >= 2:
            return min(prices), max(prices)
    return None, None


def pl_cota_from_spread(cotacao: float, spread_pct: float) -> float:
    return cotacao / (1 + spread_pct / 100)
