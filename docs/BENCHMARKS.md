# Benchmarky v0.1.1

## Lokálna simulácia

```powershell
New-Item -ItemType Directory -Force .tm-law | Out-Null
uv run --locked python -m scripts.benchmark --summary --output .tm-law/mock-benchmark.json
```

Pri použití `--output` musí nadradený adresár existovať. Bez tohto parametra ide UTF‑8 JSON na štandardný výstup. Pre Windows PowerShell 5.1 použite `--output` pri ukladaní do súboru, pretože presmerovanie konzoly môže zmeniť kódovanie. `--summary` vypíše tabuľku na štandardný chybový výstup. Predvolený beh použije dočasnú databázu, fiktívne znenia a tri scenáre s testovacím adaptérom. Čas simulácie necharakterizuje výkon modelu.

## Reálne modely

Bez `--cases` sa pri zadaní `--model` spustí krátka diagnostická otázka bez očakávanej právnej citácie. Hodí sa na meranie času a komunikácie, právnu kvalitu neposudzuje. Na laptop najprv spustite iba 4B model s kontextom 2 048:

```powershell
New-Item -ItemType Directory -Force .tm-law | Out-Null
uv run --locked python -m scripts.benchmark --model qwen3.5:4b --context-window 2048 --reasoning off --reasoning on --repeats 2 --measure-memory --summary --output .tm-law/qwen-4b-2048.json
```

Po stabilnom behu porovnajte ďalšie lokálne nainštalované tagy a kontexty. Jeden proces benchmarku posiela požiadavky postupne a každá žiada Ollamu o uvoľnenie modelu po odpovedi (`keep_alive=0`). Zatvorte paralelné chaty. Spustite Ollamu s `OLLAMA_MAX_LOADED_MODELS=1` a `OLLAMA_NUM_PARALLEL=1`. Najvyšší kontext 8 192 skúšajte až po kontrole rezervy pamäte.

Ak má proces vidieť viac vlákien, než je kvóta CPU, Ollama ich môže všetky použiť a odpoveď vyčerpá časový limit. Predvolený príkaz parameter `num_thread` neposiela. Dve vlákna vynútite takto:

```powershell
uv run --locked python -m scripts.benchmark --model qwen3.5:4b --context-window 2048 --device cpu --num-threads 2 --summary --output .tm-law/qwen-2-threads.json
.\scripts\benchmark-windows.ps1 -Model qwen3.5:4b -Threads 2
```

`--num-threads` je celé číslo od 1 do 256. Report ho zapíše do `settings.cpu_threads`. Vynechanie voľby znamená `null` a doterajšie správanie. Rovnaký limit pre bežnú aplikáciu nastaví premenná `TM_LAW_OLLAMA_NUM_THREADS`. Samotný benchmark túto premennú nečíta. Explicitná hodnota v požiadavke má prednosť pred premennou. Neplatná premenná zastaví otázku ešte pred volaním Ollamy.

Každá pasáž v zadaní pre model obsahuje krátku citačnú značku `[S1]`, `[S2]` a podobne. Rovnaká značka je aj na konci úryvku v prompte. Citačná karta zobrazuje pôvodný úryvok. Značka platí iba v rámci danej odpovede a server ju preloží na stabilný identifikátor skutočne vloženej pasáže. Prijíma aj úplné identifikátory v jednoduchých a dvojitých hranatých zátvorkách, keď patria do kontextu danej odpovede. Pri porovnaní behov používajte stabilné identifikátory z reportu.

`--mmap` alebo `--no-mmap` explicitne nastaví Ollame mapovanie súboru váh. Bez voľby rozhoduje runtime. Benchmark zapíše hodnotu do `settings.ollama_use_mmap`. Merajte vplyv pri rovnakom modeli, korpuse a otázke. Pamäť mapovaná zo súboru môže byť súčasťou PSS aj súborovej cache. [Cloudové meranie](CLOUD_BENCHMARK_2026-11-19.md)

```powershell
uv run --locked python -m scripts.benchmark --model qwen3.5:4b --model qwen3.5:9b --model abliterant/qwen3.5-rana:9b --context-window 4096 --reasoning auto --summary --output .tm-law/modely.json
```

Pre právne porovnanie pridajte `--cases overene.jsonl --data-dir .tm-law/praca`. Formát úloh vychádza z [ukážkového JSONL](../benchmarks/smoke.jsonl). Vyžadované sú `id`, `category`, `question` a `expected_sources`. Pri hodnotení historického znenia použite kategóriu `historické znenia` a presný `as_of`. Zadajte `expert_verified` iba pri odborne overenej referencii. Fiktívne úlohy sa pri reálnej inferencii vylúčia. Pred porovnaním nástroj urobí jednu snímku právnej databázy bez databázy súkromných dokumentov. Zapíše hash korpusu a vstupných úloh, modelový digest podľa Ollamy a parametre, vrátane `--seed`, `--temperature`, `--max-tokens` a `--num-threads`. Rovnaký seed nezaručuje identický výstup na rôznom hardvéri.

Výstup obsahuje stav, dĺžkový limit, latenciu, čas k prvému tokenu a k prvému viditeľnému tokenu, počet tokenov a rýchlosť podľa runtime. Pri zapnutom uvažovaní počet generovaných tokenov môže zahŕňať aj interné tokeny. Validita citačných identifikátorov, záchyt zdrojov a zhoda historických ID hodnotia identifikátory. Polia pre odborné posúdenie právnej správnosti a úplnosti sú prázdne, kým ich nevyplní hodnotiteľ. Príznak ukončenia generovania sám neurčuje odbornú úplnosť.

Predvolený report neobsahuje otázky ani odpovede. Text odpovedí pripojí len `--include-answers`. Aj identifikátory a názvy benchmarkových úloh môžu byť citlivé. Na meranie používajte verejné alebo výslovne schválené testovacie údaje a reporty ukladajte mimo Gitu.

## Interpretácia pamäte

| Metrika | Význam |
| --- | --- |
| Špičkové RSS procesu | Najvyššia pozorovaná rezidentná pamäť medzi snímkami. Na Windows ide o working set. Môže zahŕňať zdieľané stránky. |
| Špičkové USS procesu | Pozorovaná pamäť jedinečná pre proces, ak ju OS sprístupní. Nezahŕňa zdieľanú časť. |
| Spoločná špička PSS | Súčet pomerných podielov zdieľaných stránok z jednej snímky, keď sa podarí priradiť lokálny Ollama listener aj procesy potomkov a OS sprístupní PSS. Na Windows sa zvyčajne nevykazuje. |
| Pamäť celého systému | Pozorované `total - available` z psutil. Zahŕňa aj procesy mimo TM‑Law a Ollamy. |

Snímky sa zbierajú každých 0,5 sekundy počas voliteľného merania. Krátke špičky medzi snímkami môžu uniknúť. RSS nesčítavame. Virtuálna pamäť je adresný priestor a veľkosť súboru váh je disková metrika. Ani jedna nevyjadruje spotrebu fyzickej RAM. Prehliadač, iné procesy, nepriradené WSL procesy a zdieľaná pamäť iGPU môžu zostať mimo odhadu. Pri neznámom celku nemožno potvrdiť limit 12 GB iba z RSS.

| Model | Uvažovanie | RAM | Tok/s | Latencia |
| --- | --- | --- | --- | --- |
| Qwen3.5 4B | off / on, podľa podpory | Zmerať na Lenovo | Zmerať | Zmerať |
| Qwen3.5 9B | off / on, podľa podpory | Zmerať na Lenovo | Zmerať | Zmerať |
| Qwen3.5 RANA 9B | off / on, podľa podpory | Zmerať na Lenovo | Zmerať | Zmerať |

## Slovenská sada a nezávislé hodnotenie

[Štartovacia sada](../benchmarks/slovak-starter.jsonl) obsahuje **13 syntetických scenárov**. Tri používajú fiktívnu právnu zbierku. Zvyšných desať skúša prácu s chýbajúcimi podkladmi, faktami a slovenskou terminológiou. Právne normy ani odborné hodnotenie sa im nepripisujú. Cieľ 200 overených položiek vyžaduje dostupné reálne zdroje a odborných hodnotiteľov.

```powershell
uv run --locked python -m scripts.benchmark --cases benchmarks/slovak-starter.jsonl --summary
```

Voliteľné polia sú `difficulty`, `scenario_type`, `provenance`, `source_groups`, `required_characteristics`, `forbidden_sources` a `expected_evidence`. `fictional` označuje fiktívne právne materiály, ktoré sa nepoužijú pri reálnej inferencii. Syntetický skutkový scenár môže mať aj pravé právne zdroje. Pri autentických referenciách doplňte konkrétny dátum, identifikátory, pôvod a vyžadovanú odpoveď. Skutočné odborné overenie označte až po zhodnotení referencie odborníkom.

`deterministic_checks` kontroluje záchyt očakávaných úsekov pri vyhľadávaní, ich prítomnosť v kontexte, povolené a zakázané ID, historické znenie a stav podkladov. `retrieval_recall`, `context_recall` a `expected_sources_cited` merajú podiel očakávaných referencií v každej fáze. Na spracovanie odborných hodnotení použite report so schválenými dátami a s voľbou `--include-answers`.

```powershell
uv run --locked python -m scripts.legal_review prepare --cases overene.jsonl --report .tm-law/modely.json --sheet .tm-law/posudky.json --key .tm-law/kluc.json
uv run --locked python -m scripts.legal_review aggregate --key .tm-law/kluc.json --judgments .tm-law/vyplnene.json --output .tm-law/zhodnotenie.json
```

Hodnotiteľ dostane hárok bez názvov modelov. Vráti pole JSON objektov s `review_id` a posudkom `legal_correctness`, `citation_support`, `completeness` v hodnotách `yes`, `partial`, `no` alebo `null`. Polia `unsupported_claims` a `unnecessary_refusal` sú `true`, `false` alebo `null`. Kľúč držte oddelene od hárka. Zhrnutie vykazuje iba skutočne posúdené položky. Automatická kontrola identifikátorov nepriraďuje modelu právne skóre.

## Kontrola referencií pred inferenciou

Pri úlohách s reálnymi zdrojmi použite `--audit-only` ešte pred spustením Ollamy. Kontrola prečíta snímku právnej databázy. Pri očakávaných citáciách overí existenciu pasáže, väzbu na archivovaný originál, SHA‑256 originálu a výskyt pasáže v texte. Pri rozhodujúcom dátume skontroluje dátum rozhodnutia alebo doložený interval účinnosti. Pri historickej úlohe bez rozhodujúceho dátumu kontrola zlyhá.

```powershell
uv run --locked python -m scripts.benchmark --audit-only --cases overene.jsonl --data-dir .tm-law/praca --output .tm-law/audit-zdrojov.json
uv run --locked python -m scripts.benchmark --model qwen3.5:4b --cases overene.jsonl --data-dir .tm-law/praca --require-source-audit --summary
```

Výstup auditu je objekt JSON s označením `source_audit`. Obsahuje identifikátory úloh, referencií a výsledky kontrol. Otázky ani text pasáží nezapisuje. Pri zlyhaní je návratový kód 2 a režim `--require-source-audit` nevykoná žiadnu inferenciu. Úspech vyžaduje aspoň jednu úlohu s overenými referenciami a žiadnu neúspešnú referenčnú úlohu. Fiktívne úlohy a prípady bez očakávaného zdroja sa vykazujú samostatne. Pri úspešnom behu modelu je audit súčasťou bežného JSON reportu.

Audit overuje integritu archivovaných údajov a súlad dátumov s uloženými metadátami. Pôvod záznamu, právny význam prechodných ustanovení a správnosť záveru posudzuje človek.

## Zákon o rodine

[Sada s deviatimi úlohami](../benchmarks/slovak-family-law.jsonl) má fiktívne skutkové zadania, skutočné archivované právne referencie v ôsmich úlohách a jednu negatívnu kontrolu mimo dátumového pokrytia. Pri zmene § 6 ods. 1 a § 91 ods. 2 testuje posledný deň staršieho a prvý deň novšieho znenia. Zahŕňa aj prípad s prechodným ustanovením. Žiadna úloha zatiaľ nemá odborný posudok.

Po [offline importe](LEGAL_CORPUS_STATUS.md) overte odkazy bez spustenia modelu:

```powershell
uv run --locked --offline python -m scripts.benchmark --audit-only --cases benchmarks/slovak-family-law.jsonl --data-dir .tm-law/slovlex --output .tm-law/family-law-source-audit.json
```

Pri príprave tréningových dát pridajte aj `--holdout benchmarks/slovak-family-law.jsonl`. Na súvisiacich tréningových príkladoch používajte rovnakú skupinu `sk-zz-2005-36`, aby sa príbuzné znenia nedostali do tréningu s touto vyhradenou sadou. [Príprava tréningu](TRAINING.md)

## Cloudové porovnanie

Sada `slovak-cloud-law.jsonl` má päť testovacích otázok nad autentickou zbierkou. Obsahuje dvojitý odkaz na odseky jedného paragrafu, výber ústavného znenia na hranici účinnosti a kontrolu dňa mimo pokrytia. Tri prípady majú štyri očakávané referencie. Pri zvyšných dvoch sa očakáva chýbajúci podklad. [Otázky](../benchmarks/slovak-cloud-law.jsonl) · [Technický report](CLOUD_BENCHMARK_2026-11-19.md)
