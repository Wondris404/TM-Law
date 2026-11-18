# Windows 11 (PowerShell)

Nainštalujte Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/), [Node.js 24](https://nodejs.org/) a pre skutočnú inferenciu [Ollamu](https://ollama.com/download/windows). Otvorte nový PowerShell v koreňovom adresári repozitára.

```powershell
python --version
uv --version
node --version
uv sync --locked
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

## Skúška bez váh

```powershell
uv run --locked python -m scripts.import_legal data/demo-2022.json --data-dir .tm-law/demo
uv run --locked python -m scripts.import_legal data/demo-2024.json --data-dir .tm-law/demo
$env:TM_LAW_ADAPTER = "mock"
$env:TM_LAW_DATA_DIR = ".tm-law/demo"
uv run --locked python -m uvicorn backend.tm_law.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

V prehliadači otvorte `http://127.0.0.1:8000`. V databáze vyhľadajte `9999/2099 § 7 evidencia` k `2022-12-20`. V chate vyskúšajte otázku „Ako dlho sa uchovávala evidencia dielne?“ s tým istým rozhodujúcim dátumom. Po skončení zastavte server pomocou Ctrl+C.

## Skutočný model

Zatvorte bežiacu Ollamu z oznamovacej oblasti Windows, nastavte vypnutie cloudových funkcií a spustite lokálny server. Príkaz nechajte bežať v samostatnom PowerShelli:

```powershell
$env:OLLAMA_NO_CLOUD = "1"
$env:OLLAMA_HOST = "127.0.0.1:11434"
ollama serve
```

Prvé stiahnutie váh potrebuje prístup na internet. V druhom PowerShelli, z koreňa repozitára:

```powershell
ollama pull qwen3.5:4b
ollama list
$env:TM_LAW_ADAPTER = "ollama"
$env:TM_LAW_DATA_DIR = ".tm-law/praca"
$env:TM_LAW_MODEL = "qwen3.5:4b"
uv run --locked python -m uvicorn backend.tm_law.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Pre lokálny model z RANA použite `ollama pull abliterant/qwen3.5-rana:9b` a jeho tag vyberte v nastaveniach TM-Law. Pre právne vyhľadávanie importujte overené znenia do pracovného adresára. Pri každom náročnejšom teste sledujte celkovú RAM a latenciu.

Voliteľná skúška modelu po stiahnutí váh:

```powershell
$env:TM_LAW_TEST_OLLAMA_MODEL = "qwen3.5:4b"
uv run --locked pytest -q -m ollama
```

Inštalácia uzamknutých balíkov, zostavenie, štart a tok simulácie boli overené na Linuxe. PowerShell syntax a inferenciu na cieľovom Windows zariadení treba ešte overiť. Windows job v CI pokrýva Python, FTS5 a parsovanie súborov.
