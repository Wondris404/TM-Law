"""Read public web evidence for an explicitly submitted research query."""

import asyncio
import hashlib
import html
import json
import re
import subprocess
import unicodedata
from datetime import UTC, datetime

import httpx

from .corpus import VisibleSourceText, original_text
from .schemas import WebResearchInput

SITES = {
    "all": (
        "slov-lex.sk",
        "justice.gov.sk",
        "eur-lex.europa.eu",
        "orsr.sk",
        "registeruz.sk",
        "nbs.sk",
        "statistics.sk",
        "ec.europa.eu",
    ),
    "law": (
        "slov-lex.sk",
        "justice.gov.sk",
        "nsud.sk",
        "nssud.sk",
        "ustavnysud.sk",
        "eur-lex.europa.eu",
        "curia.europa.eu",
        "hudoc.echr.coe.int",
        "nrsr.sk",
    ),
    "business": (
        "orsr.sk",
        "registeruz.sk",
        "rpo.statistics.sk",
        "rpvs.gov.sk",
        "justice.gov.sk",
        "replik.justice.sk",
        "crz.gov.sk",
        "uvo.gov.sk",
    ),
    "economy": (
        "nbs.sk",
        "statistics.sk",
        "ec.europa.eu",
        "data.ecb.europa.eu",
        "financnasprava.sk",
        "mfsr.sk",
    ),
}
PUBLIC_HOSTS = frozenset(
    {host for group in SITES.values() for domain in group for host in (domain, f"www.{domain}")}
    | {
        "api.statistics.sk",
        "static.slov-lex.sk",
        "sluzby.orsr.sk",
        "obcan.justice.sk",
        "obchodnyvestnik.justice.gov.sk",
        "infocuria.curia.europa.eu",
        "ec.europa.eu",
        "data.ecb.europa.eu",
        "subjekty.nbs.sk",
        "openstats.nbs.sk",
        "slovak.statistics.sk",
        "statdat.statistics.sk",
        "datacube.statistics.sk",
        "portal.uvo.gov.sk",
    }
)
BRAVE = httpx.URL("https://api.search.brave.com/res/v1/web/search")
RPO = httpx.URL("https://api.statistics.sk/rpo/v1/search")
ORSR = httpx.URL("https://www.orsr.sk/hladaj_ico.asp")
RUZ = httpx.URL("https://www.registeruz.sk/cruz-public/api/")
ICO = re.compile(r"(?:ičo\s*[:=]?\s*|ico\s*[:=]?\s*)?([0-9]{8})", re.I)
ERRORS = (httpx.HTTPError, httpx.InvalidURL, ValueError, TimeoutError, subprocess.TimeoutExpired)
MAX_BYTES = 4 * 1024 * 1024
MAX_PAGES = 6
REDIRECT_CODES = {301, 302, 303, 307, 308}


class PublicPageText(VisibleSourceText):
    blocks = VisibleSourceText.blocks | {"main", "th", "table", "dl", "dt", "dd", "h5"}
    excluded = VisibleSourceText.excluded | {
        "header",
        "nav",
        "footer",
        "aside",
        "noscript",
        "svg",
        "iframe",
    }

    def __init__(self):
        super().__init__()
        self.saw_heading = False

    def handle_starttag(self, tag, attrs):
        if tag == "h1" and self.hidden is None and not self.saw_heading:
            self.parts.clear()
            self.saw_heading = True
        super().handle_starttag(tag, attrs)


def public_url(value: str | httpx.URL) -> httpx.URL:
    try:
        url = httpx.URL(value)
    except (httpx.InvalidURL, TypeError) as exc:
        raise ValueError("Webový odkaz má neplatný formát.") from exc
    if (
        url.scheme != "https"
        or url.host not in PUBLIC_HOSTS
        or url.userinfo
        or url.port is not None
    ):
        raise ValueError("Webová rešerš podporuje verejné HTTPS adresy zo zoznamu zdrojov.")
    return url.copy_with(fragment=None)


async def read_resource(
    client: httpx.AsyncClient, url: httpx.URL, *, params=None, brave_key: str | None = None
) -> tuple[httpx.URL, str, bytes]:
    if brave_key and url != BRAVE:
        raise ValueError("Kľúč patrí iba vyhľadávaču.")
    if not brave_key:
        url = public_url(url)
    headers = {"X-Subscription-Token": brave_key} if brave_key else None
    async with asyncio.timeout(8):
        for _ in range(4):
            async with client.stream("GET", url, params=params, headers=headers) as response:
                if not brave_key and response.status_code in REDIRECT_CODES:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Zdroj neposkytol adresu presmerovania.")
                    url = public_url(response.url.join(location))
                    params = None
                    continue
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise ValueError("Zdroj presiahol limit veľkosti.")
                return response.url, response.headers.get("content-type", ""), bytes(data)
    raise ValueError("Webový zdroj má priveľa presmerovaní.")


async def read_json(client, url, *, params=None, brave_key=None) -> tuple[httpx.URL, dict]:
    address, _, data = await read_resource(client, url, params=params, brave_key=brave_key)
    decoded = json.loads(data)
    if not isinstance(decoded, dict):
        raise ValueError("Zdroj nevrátil očakávaný formát JSON.")
    return address, decoded


def json_records(value: object) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def source(url: httpx.URL, title: str, authority: str, text: str) -> dict:
    digest = hashlib.sha256(f"{url}\n{text}".encode()).hexdigest()[:24]
    version = f"web-{digest}"
    return {
        "citation_id": f"{version}/extract",
        "version_id": version,
        "title": title[:240],
        "kind": "web",
        "authority": authority,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_url": str(url),
        "text": text,
        "fictional": False,
        "open_ended": False,
        "original_archived": False,
        **dict.fromkeys(
            (
                "law_number",
                "law_year",
                "section",
                "paragraph",
                "letter",
                "effective_from",
                "effective_until",
                "case_number",
                "decision_date",
                "norm_status",
            )
        ),
    }


def words(text: str) -> set[str]:
    bare = "".join(
        c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)
    )
    return set(re.findall(r"\b(?:[a-z]{3,}|\d+)\b", bare))


def relevant_text(text: str, focus: str) -> str:
    text = "\n".join(line for raw in text.splitlines() if (line := " ".join(raw.split())))
    terms = words(focus)
    passages = [text[i : i + 1150] for i in range(0, len(text), 850)]
    return max(passages, key=lambda part: len(words(part) & terms), default="").strip()


def html_content(data: bytes, content_type: str, host: str) -> tuple[str, str]:
    charset = re.search(rb"charset\s*=\s*['\"]?([\w-]+)", data[:8192], re.I)
    header_charset = re.search(r"charset\s*=\s*['\"]?([\w-]+)", content_type, re.I)
    encoding = (
        header_charset[1]
        if header_charset
        else charset[1].decode("ascii")
        if charset
        else "cp1250"
        if host.endswith(".orsr.sk")
        else "utf-8"
    )
    try:
        decoded = data.decode(encoding, errors="replace")
    except LookupError:
        decoded = data.decode("utf-8", errors="replace")
    title_match = re.search(r"<title\b[^>]*>(.*?)</title\s*>", decoded, re.I | re.S)
    title = " ".join(html.unescape(title_match[1]).split()) if title_match else host
    parser = PublicPageText()
    parser.feed(decoded)
    parser.close()
    return title, "".join(parser.parts)


async def read_page(client, url: httpx.URL, focus: str) -> dict:
    address, content_type, data = await read_resource(client, url)
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime == "application/pdf":
        title = address.path.rsplit("/", 1)[-1] or address.host
        text = await asyncio.to_thread(original_text, data, ".pdf")
    elif mime in {"text/html", "application/xhtml+xml"}:
        title, text = html_content(data, content_type, address.host)
    elif mime == "text/plain":
        title, text = address.host, data.decode("utf-8-sig", errors="replace")
    else:
        raise ValueError("Zdroj má nepodporovaný formát.")
    excerpt = relevant_text(text, focus)
    if len(excerpt) < 45:
        raise ValueError("Zdroj neposkytol použiteľný text.")
    return source(address, title, address.host, excerpt)


def rpo_name(record: dict) -> str:
    names = [
        item for item in json_records(record.get("fullNames")) if isinstance(item.get("value"), str)
    ]
    return max(
        names,
        key=lambda item: (not item.get("validTo"), str(item.get("validFrom") or "")),
        default={},
    ).get("value", "Názov neuvedený")


async def rpo_lookup(client, ico: str) -> dict:
    address, data = await read_json(client, RPO, params={"identifier": ico, "limit": 10})
    records = [
        row
        for row in json_records(data.get("results"))
        if any(item.get("value") == ico for item in json_records(row.get("identifiers")))
    ]
    if not records:
        raise ValueError("RPO nevrátil zodpovedajúci záznam.")
    lines = [f"IČO {ico}. Výsledky RPO, zobrazené záznamy: {min(len(records), 5)}."]
    for row in sorted(records, key=lambda row: bool(row.get("termination")))[:5]:
        name = rpo_name(row)
        start = row.get("establishment") or "neuvedený"
        end = row.get("termination") or "neuvedený"
        lines.append(f"{name} | vznik {start} | zánik {end} | ID RPO {row.get('id')}")
    return source(address, f"RPO · IČO {ico}", "Štatistický úrad SR", "\n".join(lines))


async def ruz_lookup(client, ico: str) -> dict:
    address, index = await read_json(
        client,
        RUZ.join("uctovne-jednotky"),
        params={"zmenene-od": "2000-01-01", "ico": ico, "max-zaznamov": 3},
    )
    ids = index.get("id", [])
    if not isinstance(ids, list) or not ids or any(type(item) is not int for item in ids):
        raise ValueError("RÚZ nevrátil zodpovedajúcu účtovnú jednotku.")
    if len(ids) != 1 or index.get("existujeDalsieId"):
        return source(
            address,
            f"RÚZ · IČO {ico}",
            "Register účtovných závierok",
            f"IČO {ico}: register vrátil viac účtovných jednotiek. ID na overenie: {ids[:3]}.",
        )
    _, row = await read_json(client, RUZ.join("uctovna-jednotka"), params={"id": ids[0]})
    if row.get("ico") != ico:
        raise ValueError("IČO účtovnej jednotky sa nezhoduje.")
    fields = {
        "nazovUJ": "Účtovná jednotka",
        "ico": "IČO",
        "datumZalozenia": "Dátum založenia",
        "datumZrusenia": "Dátum zrušenia",
        "mesto": "Obec",
        "datumPoslednejUpravy": "Posledná úprava záznamu",
    }
    lines = [f"{label}: {row[key]}" for key, label in fields.items() if row.get(key)]
    for key, label in (
        ("idUctovnychZavierok", "závierok"),
        ("idVyrocnychSprav", "výročných správ"),
    ):
        documents = row.get(key)
        if isinstance(documents, list):
            lines.append(f"Počet ID {label} v zázname: {len(documents)}.")
    portal = httpx.URL(
        f"https://www.registeruz.sk/cruz-public/domain/accountingentity/show/{ids[0]}"
    )
    return source(portal, f"RÚZ · IČO {ico}", "Register účtovných závierok", "\n".join(lines))


async def orsr_lookup(client, ico: str, focus: str) -> dict:
    address, content_type, data = await read_resource(client, ORSR, params={"ICO": ico, "SID": 0})
    details = set(
        re.findall(rb"\bvypis\.asp\?ID=\d+(?:&amp;|&)SID=\d+(?:&amp;|&)P=0\b", data, re.I)
    )
    if len(details) == 1:
        detail = address.join(html.unescape(details.pop().decode("ascii")))
        try:
            return await read_page(client, detail, f"{focus} {ico} sídlo oddiel vložka vznik")
        except ERRORS:
            # The search result remains usable when the record detail cannot be read.
            pass
    _, text = html_content(data, content_type, address.host)
    excerpt = relevant_text(text, f"{ico} záznamy obchodné meno aktuálny úplný")
    if not excerpt:
        raise ValueError("Obchodný register neposkytol čitateľný výsledok.")
    return source(address, f"Obchodný register · IČO {ico}", "Obchodný register SR", excerpt)


class WebResearch:
    def __init__(self, brave_key: str = "", transport: httpx.AsyncBaseTransport | None = None):
        self.brave_key = brave_key.strip()
        self.transport = transport

    async def run(self, request: WebResearchInput, *, focus: str) -> tuple[list[dict], list[str]]:
        async with httpx.AsyncClient(
            transport=self.transport,
            timeout=5,
            follow_redirects=False,
            headers={"User-Agent": "TM-Law/0.1.2 public research", "Accept-Encoding": "identity"},
        ) as client:
            match = ICO.fullmatch(request.query)
            if match:
                tasks = [
                    ("Obchodný register", orsr_lookup(client, match[1], focus)),
                    ("RPO", rpo_lookup(client, match[1])),
                    ("RÚZ", ruz_lookup(client, match[1])),
                ]
            elif re.match(r"^[a-z][a-z0-9+.-]*://", request.query, re.I):
                try:
                    url = public_url(request.query)
                except ValueError as exc:
                    return [], [str(exc)]
                tasks = [(url.host, read_page(client, url, focus))]
            else:
                if not self.brave_key:
                    return [], [
                        "Textové vyhľadávanie vyžaduje Brave Search API. Zadajte verejné IČO alebo HTTPS adresu."
                    ]
                try:
                    urls = await self.search(client, request)
                except ERRORS:
                    return [], [
                        "Brave Search neposkytol výsledky. Overte kľúč a dostupnosť služby."
                    ]
                if not urls:
                    return [], [
                        "Vyhľadávač nenašiel stránku z podporovaných zdrojov v zvolenej oblasti."
                    ]
                tasks = [
                    (url.host, read_page(client, url, focus + " " + request.query)) for url in urls
                ]
            results = await asyncio.gather(*(task for _, task in tasks), return_exceptions=True)
        sources, notes = [], []
        for (name, _), result in zip(tasks, results, strict=True):
            if isinstance(result, httpx.HTTPStatusError):
                notes.append(f"{name}: zdroj vrátil HTTP {result.response.status_code}.")
            elif isinstance(result, ERRORS):
                notes.append(
                    f"{name}: pri tomto dopyte sa nepodarilo získať použiteľný webový podklad."
                )
            elif isinstance(result, BaseException):
                raise result
            elif not any(item["source_url"] == result["source_url"] for item in sources):
                sources.append(result)
        return sources, list(dict.fromkeys(notes))

    async def search(self, client: httpx.AsyncClient, request: WebResearchInput) -> list[httpx.URL]:
        scopes = SITES[request.scope]
        clause = " OR ".join(f"site:{domain}" for domain in scopes)
        scoped_query = f"{request.query} ({clause})"
        query = (
            scoped_query
            if len(scoped_query) <= 400 and len(scoped_query.split()) <= 50
            else request.query
        )
        _, payload = await read_json(
            client,
            BRAVE,
            params={"q": query, "count": 15, "search_lang": "sk", "text_decorations": "false"},
            brave_key=self.brave_key,
        )
        urls: list[httpx.URL] = []
        overflow: list[httpx.URL] = []
        web = payload.get("web")
        for result in json_records(web.get("results") if isinstance(web, dict) else None):
            try:
                candidate = public_url(result.get("url", ""))
            except ValueError:
                continue
            if request.scope != "all" and not any(
                candidate.host == domain or candidate.host.endswith(f".{domain}")
                for domain in scopes
            ):
                continue
            if candidate in urls or candidate in overflow:
                continue
            if any(
                item.host.removeprefix("www.") == candidate.host.removeprefix("www.")
                for item in urls
            ):
                overflow.append(candidate)
            else:
                urls.append(candidate)
        return (urls + overflow)[:MAX_PAGES]
