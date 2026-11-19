"""Select a TM-Law workflow and optionally read a pinned upstream skill."""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path, PurePosixPath

import httpx

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / ".agents/skills/github-skill-selector/references/catalog.json"
GITHUB = "https://github.com"
RAW_GITHUB = "https://raw.githubusercontent.com"
MAX_SKILL_BYTES = 128 * 1024


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    plain = "".join(
        char
        for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def matched_keywords(task: str, keywords: list[str]) -> list[str]:
    matched = []
    for keyword in keywords:
        tokens = normalize(keyword).split()
        if not tokens:
            continue
        suffix = "" if keyword.isupper() else r"[a-z0-9]*"
        pattern = r"\b" + " ".join(re.escape(token) + suffix for token in tokens) + r"\b"
        if re.search(pattern, task):
            matched.append(keyword)
    return matched


def infer_intent(catalog: dict, task: str) -> tuple[str, list[str]] | None:
    normalized = normalize(task)
    candidates = []
    for intent, definition in catalog["intents"].items():
        matches = matched_keywords(normalized, definition["keywords"])
        if matches:
            lengths = [len(normalize(phrase).split()) for phrase in matches]
            candidates.append(
                ((max(lengths), sum(length**2 for length in lengths)), intent, matches)
            )
    if not candidates:
        return None
    _, intent, matches = max(candidates, key=lambda item: item[0])
    return intent, matches


def upstream_links(repo: str, revision: str, path: str) -> dict[str, str]:
    segments = [*repo.split("/"), *path.split("/")]
    if (
        len(repo.split("/")) != 2
        or any(
            not re.fullmatch(r"[A-Za-z0-9_.-]+", part) or part in {".", ".."} for part in segments
        )
        or not re.fullmatch(r"[0-9a-f]{40}", revision)
        or PurePosixPath(path).name != "SKILL.md"
    ):
        raise ValueError("Katalóg neobsahuje platnú pripnutú adresu skillu.")
    return {
        "url": f"{GITHUB}/{repo}/blob/{revision}/{path}",
        "raw_url": f"{RAW_GITHUB}/{repo}/{revision}/{path}",
    }


def public_resource(row: dict, *, intent: str | None = None) -> dict:
    item = {key: row[key] for key in ("repo", "name", "kind", "use")}
    item["url"] = f"{GITHUB}/{row['repo']}"
    upstream = row.get("upstream")
    if upstream and (intent is None or intent in upstream["intents"]):
        item["upstream"] = {
            **upstream,
            **upstream_links(row["repo"], upstream["revision"], upstream["path"]),
        }
    return item


def select(catalog: dict, task: str, *, intent: str | None = None, repo: str | None = None) -> dict:
    inferred = infer_intent(catalog, task) if intent is None else (intent, [])
    if inferred is None:
        return {"intent": None, "status": "no-match"}
    intent, matches = inferred
    definition = catalog["intents"][intent]
    by_repo = {item["repo"]: item for item in catalog["resources"]}
    candidates = definition["resources"]
    if repo is not None:
        if repo not in candidates:
            raise ValueError("Repozitár nie je v katalógu priradený k tomuto zámeru.")
        candidates = [repo, *(candidate for candidate in candidates if candidate != repo)]
    resources = [public_resource(by_repo[candidate], intent=intent) for candidate in candidates]
    return {
        "intent": intent,
        "title": definition["title"],
        "matched": matches,
        "local_skills": [f".agents/skills/{name}/SKILL.md" for name in definition["local_skills"]],
        "primary": resources[0],
        "alternatives": resources[1:],
    }


def read_upstream(skill: dict, *, transport: httpx.BaseTransport | None = None) -> str:
    # Reconstruct the URL from the catalog identity and pinned revision.
    link = upstream_links(skill["repo"], skill["revision"], skill["path"])["raw_url"]
    data = bytearray()
    with httpx.Client(timeout=8, follow_redirects=False, transport=transport) as client:
        with client.stream("GET", link) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size=8192):
                data.extend(chunk)
                if len(data) > MAX_SKILL_BYTES:
                    raise ValueError("GitHub skill prekročil limit veľkosti.")
    text = data.decode("utf-8-sig")
    frontmatter = text.split("---", 2)
    if (
        len(frontmatter) != 3
        or frontmatter[0]
        or not re.search(r"^name:\s*" + re.escape(skill["name"]) + r"\s*$", frontmatter[1], re.M)
    ):
        raise ValueError("Obsah skillu na GitHube sa nezhoduje s katalógom.")
    return text


def render_markdown(catalog: dict) -> str:
    parts = [
        "# Knižnica GitHub zdrojov pre TM-Law",
        "",
        f"Katalóg obsahuje **{len(catalog['resources'])} repozitárov** a "
        f"**{sum('upstream' in item for item in catalog['resources'])} pripnutých GitHub skillov**.",
        "Typ pri položke označuje jej využitie v TM-Law. Odkaz v stĺpci Skill vedie na konkrétny "
        "commit pôvodného návodu.",
        "",
        "V Codexe použi [$github-skill-selector](../.agents/skills/github-skill-selector/SKILL.md). "
        "Strojový zoznam a mapovanie úloh sú v [catalog.json]"
        "(../.agents/skills/github-skill-selector/references/catalog.json).",
        "",
    ]
    for group, title in catalog["groups"].items():
        parts.extend(
            [
                f"## {title}",
                "",
                "| Repozitár | Typ | Použitie v TM-Law | Skill |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in catalog["resources"]:
            if row["group"] != group:
                continue
            item = public_resource(row)
            upstream = item.get("upstream")
            link = f"[{upstream['name']}]({upstream['url']})" if upstream else "—"
            parts.append(
                f"| [{item['repo']}]({item['url']}) | {item['kind']} | {item['use']} | {link} |"
            )
        parts.append("")
    return "\n".join(parts)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    catalog = load_catalog()
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    route = command.add_parser("select", help="Vyber zdroje podľa zadania alebo známeho zámeru.")
    route.add_argument("task", nargs="?", default="")
    route.add_argument("--intent", choices=catalog["intents"])
    route.add_argument("--repo", help="Uprednostni dostupný repozitár priradený k zámeru.")
    route.add_argument("--read-upstream", action="store_true")
    markdown = command.add_parser("markdown", help="Vygeneruj prehľad knižnice.")
    markdown.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "markdown":
        rendered = render_markdown(catalog)
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return
    if not args.task.strip() and args.intent is None:
        parser.error("Zadajte úlohu alebo --intent.")
    try:
        result = select(catalog, args.task, intent=args.intent, repo=args.repo)
    except ValueError as exc:
        parser.error(str(exc))
    primary = result.get("primary", {})
    if args.read_upstream and "upstream" in primary:
        skill = {"repo": primary["repo"], **primary["upstream"]}
        try:
            result["upstream_text"] = read_upstream(skill)
        except (httpx.HTTPError, ValueError):
            result["upstream_status"] = (
                "Pripnutý skill sa nepodarilo načítať. Použi dostupný postup."
            )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
