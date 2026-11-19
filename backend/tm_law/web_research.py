"""Read public web evidence for an explicitly submitted research query."""

import asyncio
import hashlib
import html
import json
import re
import subprocess
import unicodedata
from datetime import UTC, datetime
from itertools import zip_longest

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
BRAVE_CONTEXT = httpx.URL("https://api.search.brave.com/res/v1/llm/context")
RPO = httpx.URL("https://api.statistics.sk/rpo/v1/search")
ORSR = httpx.URL("https://www.orsr.sk/hladaj_ico.asp")
RUZ = httpx.URL("https://www.registeruz.sk/cruz-public/api/")
ICO = re.compile(r"(?:ičo\s*[:=]?\s*|ico\s*[:=]?\s*)?([0-9]{8})", re.I)
ERRORS = (httpx.HTTPError, httpx.InvalidURL, ValueError, TimeoutError, subprocess.TimeoutExpired)
MAX_BYTES = 4 * 1024 * 1024
MAX_PAGES = 6
MAX_RESEARCH_QUERIES = 3
REDIRECT_CODES = {301, 302, 303, 307, 308}
PUBLIC_LINK_HOST = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})"
)
PRIVATE_SUFFIXES = {
    "arpa",
    "corp",
    "example",
    "home",
    "internal",
    "invalid",
    "lan",
    "local",
    "localhost",
    "onion",
    "test",
}


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
    if brave_key and url not in (BRAVE, BRAVE_CONTEXT):
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


def indexed_url(value: object) -> httpx.URL:
    """Validate a citation URL returned by the index. The backend does not fetch it."""
    if not isinstance(value, str) or len(value) > 2000:
        raise ValueError("Neplatný odkaz v indexe.")
    try:
        url = httpx.URL(value)
    except httpx.InvalidURL as exc:
        raise ValueError("Neplatný odkaz v indexe.") from exc
    host = url.raw_host.decode("ascii")
    if (
        url.scheme != "https"
        or url.userinfo
        or url.port is not None
        or not PUBLIC_LINK_HOST.fullmatch(host)
        or host.rsplit(".", 1)[-1] in PRIVATE_SUFFIXES
    ):
        raise ValueError("Index musí odkazovať na verejnú HTTPS stránku.")
    return url.copy_with(fragment=None)


def indexed_sources(payload: dict, focus: str) -> list[dict]:
    grounding = payload.get("grounding")
    metadata = payload.get("sources")
    terms = words(focus)
    results = []
    for item in json_records(grounding.get("generic") if isinstance(grounding, dict) else None):
        try:
            url = indexed_url(item.get("url"))
        except ValueError:
            continue
        snippets = item.get("snippets")
        if not isinstance(snippets, list):
            continue
        excerpts = [relevant_text(text, focus)[:900] for text in snippets if isinstance(text, str)]
        excerpt = max(excerpts, key=lambda text: len(words(text) & terms), default="")
        if len(excerpt) < 45:
            continue
        title = item.get("title")
        record = source(
            url, title if isinstance(title, str) and title.strip() else url.host, url.host, excerpt
        )
        record["web_reader"] = "brave_index"
        site = metadata.get(item["url"]) if isinstance(metadata, dict) else None
        timestamp = site.get("fetched_content_timestamp") if isinstance(site, dict) else None
        if type(timestamp) is int and 0 < timestamp <= datetime.now(UTC).timestamp():
            record["indexed_at"] = datetime.fromtimestamp(timestamp, UTC).isoformat(
                timespec="seconds"
            )
        results.append(record)
    return results


def distinct_sources(batches: list[list[dict]]) -> list[dict]:
    first, overflow = [], []
    urls, extracts, hosts = set(), set(), set()
    for row in zip_longest(*batches):
        for item in row:
            if item is None:
                continue
            address = item["source_url"]
            excerpt = " ".join(item["text"].casefold().split())
            if address in urls or excerpt in extracts:
                continue
            host = item["authority"].removeprefix("www.")
            (overflow if host in hosts else first).append(item)
            urls.add(address)
            extracts.add(excerpt)
            hosts.add(host)
    return (first + overflow)[:MAX_PAGES]


def next_research_query(public_query: str, attempted: list[str], sources: list[dict]) -> str | None:
    facets = list(
        dict.fromkeys(
            part.strip() for part in re.split(r"[;?\n]+", public_query) if len(words(part)) >= 2
        )
    )
    coverage = {}
    for facet in facets if len(facets) > 1 else []:
        if facet in attempted:
            continue
        terms = words(facet)
        matching_hosts = {
            item["authority"].removeprefix("www.")
            for item in sources
            if 2 * len(terms & words(item["title"] + " " + item["text"])) >= len(terms)
        }
        if len(matching_hosts) < 2:
            coverage[facet] = len(matching_hosts)
    if coverage:
        return min(coverage, key=coverage.__getitem__)
    if len(attempted) == 1 and not re.search(r"\bsite:", public_query, re.I):
        if sources:
            host = sources[0]["authority"].removeprefix("www.")
            operator = f"NOT site:{host}"
            base = " ".join(public_query.split()[:73])[: 597 - len(operator)]
            return f"({base}) {operator}"
        words_in_query = public_query.split()
        if len(words_in_query) > 8:
            return " ".join(words_in_query[:8])
    return None


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
                    if request.scope != "general":
                        return [], [str(exc)]
                    try:
                        indexed = indexed_url(request.query)
                    except ValueError as invalid:
                        return [], [str(invalid)]
                    return await self.research_web(client, request.query, focus, target=indexed)
                tasks = [(url.host, read_page(client, url, focus))]
            elif request.scope == "general":
                return await self.research_web(client, request.query, focus)
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

    async def research_web(
        self,
        client: httpx.AsyncClient,
        public_query: str,
        focus: str,
        *,
        target: httpx.URL | None = None,
    ) -> tuple[list[dict], list[str]]:
        if not self.brave_key:
            return [], [
                "Rešerš celého webu vyžaduje kľúč Brave Search API s prístupom k LLM Context."
            ]
        attempted: list[str] = []
        batches: list[list[dict]] = []
        sources: list[dict] = []
        notes: list[str] = []
        query = public_query
        for _ in range(MAX_RESEARCH_QUERIES):
            attempted.append(query)
            try:
                _, data = await read_json(
                    client,
                    BRAVE_CONTEXT,
                    params={
                        "q": " ".join(query.split()[:75]),
                        "search_lang": "sk",
                        "maximum_number_of_urls": 8,
                        "maximum_number_of_tokens": 3072,
                        "enable_source_metadata": "true",
                    },
                    brave_key=self.brave_key,
                )
            except httpx.HTTPStatusError as exc:
                notes.append(f"Brave LLM Context vrátil HTTP {exc.response.status_code}.")
                break
            except ERRORS:
                notes.append("Časť rešerše sa nepodarilo načítať z Brave LLM Context.")
                break
            batch = indexed_sources(data, f"{focus} {query}")
            if target is not None:
                sources = distinct_sources(
                    [[item for item in batch if item["source_url"] == str(target)]]
                )
                break
            batches.append(batch)
            sources = distinct_sources(batches)
            follow_up = next_research_query(public_query, attempted, sources)
            if follow_up is None:
                break
            query = follow_up
        if sources:
            notes.append(
                f"Rešerš celého webu · dopyty {len(attempted)} · vybrané zdroje {len(sources)}."
            )
        elif target is not None:
            notes.append("Index neposkytol použiteľný úryvok z tejto presnej adresy.")
        elif not notes:
            notes.append("Rešerš celého webu nenašla použiteľné podklady.")
        return sources, notes

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
