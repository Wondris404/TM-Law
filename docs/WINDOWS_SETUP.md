# Prvé spustenie na Windows 11

Nainštalujte [Git](https://git-scm.com/install/windows), [Python 3.12 alebo novší](https://www.python.org/downloads/windows/), [Node.js 24](https://nodejs.org/en/download) a [uv](https://docs.astral.sh/uv/getting-started/installation/). Pre skutočnú inferenciu použite [OllamaSetup.exe](https://ollama.com/download/windows). Ollama podporuje bežnú inštaláciu do profilu používateľa podľa [návodu pre Windows](https://docs.ollama.com/windows).

Ak máte Windows Package Manager, oficiálny návod uv uvádza tento príkaz:

```powershell
winget install --id=astral-sh.uv -e
```

Po inštalácii otvorte nový PowerShell. Pri existujúcom klone stačí prejsť do `TM-Law`, prepnúť na `main` a použiť `git pull --ff-only`.

```powershell
git clone https://github.com/Wondris404/TM-Law.git
Set-Location TM-Law
python --version
uv --version
node --version
uv sync --locked
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

## Skúška bez Ollamy

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-tm-law.ps1 -Mock
```

Spúšťač overí pripravenú aplikáciu, importuje dve výslovne fiktívne znenia do `.tm-law/demo`, spustí backend na `127.0.0.1:8000` a otvorí prehliadač. Žiadne modely nesťahuje. Nastavenie politiky sa vzťahuje na tento PowerShell proces. Ak zásady zariadenia spúšťanie skriptu zakazujú, použite nižšie uvedený ručný príkaz.

V databáze vyhľadajte `9999/2099 § 7 evidencia` k dátumu `2022-12-20` a potom k `2024-01-01`. Otázka „Ako dlho sa uchovávala evidencia dielne?“ s rozhodujúcim dátumom vráti označenú simuláciu. Tlačidlo **Merať pamäť procesov pri odpovedi** v nastaveniach pridá meranie TM‑Law aj v tomto režime. Ctrl+C ukončí backend.

## Skutočná lokálna inferencia

Ukončite už spustenú Ollamu cez oznamovaciu oblasť. V samostatnom PowerShelli nastavte loopback a obmedzte server na jeden model a jednu paralelnú požiadavku:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_NO_CLOUD = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:OLLAMA_NUM_PARALLEL = "1"
ollama serve
```

Prvé stiahnutie modelu vyžaduje sieť. Na 16 GB notebooku začnite s modelom 4B. V druhom PowerShelli, v koreňovom adresári repozitára:

```powershell
ollama pull qwen3.5:4b
ollama list
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-tm-law.ps1 -Model qwen3.5:4b
```

Spúšťač skontroluje lokálny Ollama server a prítomnosť modelu. Ak už máte iný lokálny tag, zadajte ho pomocou `-Model` alebo ho vyberte v **Nastaveniach**. Pracovná databáza je predvolene v `.tm-law/praca`. Zmenu cesty alebo portu zadajte pomocou `-DataDir` alebo `-Port`. Prepínač `-NoBrowser` ponechá spustenie prehliadača na vás. `-SmokeTest` overí štart a ihneď ukončí proces.

Ručne môžete spustiť už pripravenú aplikáciu bez spúšťača:

```powershell
$env:TM_LAW_ADAPTER = "ollama"
$env:TM_LAW_DATA_DIR = ".tm-law/praca"
$env:TM_LAW_MODEL = "qwen3.5:4b"
uv run --locked --offline --no-sync python -m uvicorn backend.tm_law.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Pri ručnej simulácii najprv importujte ukážky týmto príkazom a nastavte adaptér na `mock` a dátový adresár na `.tm-law/demo`:

```powershell
uv run --locked python -m scripts.import_legal data/demo-2022.json --data-dir .tm-law/demo
uv run --locked python -m scripts.import_legal data/demo-2024.json --data-dir .tm-law/demo
```

## Overenie offline režimu a výkonu

1. Pred odpojením siete skontrolujte tag cez `ollama list` a pripravený frontend. Ollama má bežať s `OLLAMA_NO_CLOUD=1` podľa [oficiálneho postupu](https://docs.ollama.com/faq#how-do-i-disable-ollama-s-cloud-features).
2. Odpojte Wi‑Fi a Ethernet, ponechajte lokálny server a spustite aplikáciu. Overte `Invoke-RestMethod http://127.0.0.1:11434/api/tags` a `Invoke-RestMethod http://127.0.0.1:8000/api/health`. Položte otázku nad syntetickým TXT alebo vlastným verejným zdrojom. Otváranie externých odkazov na zdroje vyžaduje sieť.
3. V nastaveniach začnite na 2 048 tokenoch, po stabilnom behu skúste 4 096 a až s dostatočnou rezervou 8 192. Porovnajte `off` a `on` iba tam, kde ich model podporuje. Pri zapnutom uvažovaní sa limit generovania môže minúť skôr, než model odpovie.
4. Zapnite meranie v aplikácii a po odpovedi otvorte **Výkon odpovede**. V Správcovi úloh sledujte fyzickú pamäť systému aj zdieľanú pamäť GPU. Výpis `ollama ps` po bežnej otázke pomôže rozlíšiť, kde je model načítaný. [Benchmarky a interpretácia metrík](BENCHMARKS.md).
5. Doplňte voliteľný integračný test. V CI sa model nesťahuje.

```powershell
$env:TM_LAW_TEST_OLLAMA_MODEL = "qwen3.5:4b"
uv run --locked --offline --no-sync pytest -q -m ollama
```

Kým neprebehne meranie na cieľovom zariadení, správanie modelu, spotreba RAM a plná offline prevádzka na ňom zostávajú neoverené. Pred prácou s klientskymi dokumentmi si prečítajte [bezpečnostné obmedzenia](SECURITY.md).

## Opakovateľný benchmark jedného modelu

Po príprave prostredia a spustení Ollamy môžete merať aj bez spusteného webového rozhrania:

```powershell
.\scripts\benchmark-windows.ps1 -Model qwen3.5:4b
.\scripts\benchmark-windows.ps1 -Model qwen3.5:4b -Contexts 2048,4096 -Reasoning off,on -Repeats 2
```

Druhý príkaz má zmysel, ak model podporuje oba režimy. Štandardne sa požaduje CPU cez `num_gpu=0`. Pri `-Device auto` rozhoduje Ollama. Údaj o umiestnení pri bežnej otázke overte cez `ollama ps`. Výsledky sa ukladajú do `.tm-law/benchmarks`. Kontext 8 192 pridajte len po kontrole rezervy pamäte. Benchmark sťahovanie modelov nespúšťa.
