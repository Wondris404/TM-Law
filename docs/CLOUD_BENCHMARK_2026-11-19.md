# TM-Law na cloudovom CPU · 19. novembra 2026

Východiskový `main` bol `3462474`. Po rozšírení korpusu bolo archivovaných šesť znení troch slovenských predpisov s 2 730 pasážami. Audit piatich testovacích otázok overil všetky štyri očakávané referencie. Dve otázky overovali chýbajúce pokrytie. [Korpus a pôvod exportov](LEGAL_CORPUS_STATUS.md) · [Benchmarkové otázky](../benchmarks/slovak-cloud-law.jsonl)

## Prostredie a obmedzenia

| Vlastnosť | Zistenie |
| --- | --- |
| OS a procesor | Debian 12, Linux 6.8, x86‑64 AMD EPYC-Genoa. Systém videl 16 jadier a cgroup mala kvótu 2 CPU. |
| Pamäť pred behom | Hostiteľ mal 30 GiB RAM a približne 24 GiB dostupných. Cgroup mala limit 4 GiB a používala približne 441 MiB. Swap bol 0. |
| Zaťaženie a disk | Pri vstupnom meraní mal hostiteľ 91 až 99 % nečinného CPU. Na súborovom systéme bolo približne 493 GiB voľných. |
| Inference | Kontajner neposkytoval GPU zariadenie. Na začiatku nebol dostupný spustiteľný Ollama server ani lokálne váhy. Použil sa CPU runtime z overeného distribučného archívu Ollama 0.40.16. |
| Vývojové nástroje | Systémový Python 3.11.2 a Node 22.23.5. Projektové kontroly prebehli na Pythone 3.12.16 z `uv sync --locked` a Node 24.22.3. |

Ollama počúvala na `127.0.0.1` a cloudové funkcie mala vypnuté. Server a benchmark mali afinitu na jedno jadro. Súčasne sa spracovávala jedna požiadavka a model sa po odpovedi uvoľnil. Vo všetkých porovnaniach mal kontext 2 048 tokenov, výstup najviac 160 tokenov, teplotu 0, seed 42 a jedno CPU vlákno. [Vydanie Ollama 0.40.16](https://github.com/ollama/ollama/releases/tag/v0.40.16)

## Výsledky reálnej inferencie

V prvom porovnaní dostali tri modely rovnakých päť slovenských otázok nad finálnou snímkou korpusu. Každá otázka sa vyhodnotila raz. Čas zahŕňa prípravu kontextu, načítanie a generovanie. PSS je špička súčtu pomernej rezidentnej pamäte backendu, Ollamy a jej detí.

| Model a nastavenie | Dokončené | Medián času | Medián času do prvého tokenu | Medián tok/s | Špička PSS | Očakávané citácie | Dĺžkový limit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5 0.5B Q4_K_M, `mmap` zapnuté | 5/5 | 10,43 s | 6,96 s | 28,26 | 618 MiB | 0/4 | 2/5 |
| Qwen2.5 1.5B Q4_K_M, `mmap` zapnuté | 5/5 | 25,20 s | 16,37 s | 17,43 | 1 813 MiB | 0/4 | 4/5 |
| Qwen3 `1.7b` Q4_K_M, `mmap` a uvažovanie vypnuté | 5/5 | 32,10 s | 18,85 s | 11,48 | 1 725 MiB | 0/4 | 2/5 |

Identifikátory váh podľa Ollamy začínali `a8b0c5157701`, `65ec06548149` a `8f68893c685c`. Ollama pri tagu `qwen3:1.7b` uviedla 2,0 miliardy parametrov. Vstup benchmarku má SHA-256 `b28e61a2e41fbf66f24724b8bc29cdfac4ead2ec258197e6c29ca0d638aae011`. Finálna snímka má odtlačok `ff2915d852d1c648b70a8a2ecf4e4b2b8adefabdb99921a2f815ae9aa5397a6c`. [Qwen2.5 0.5B](https://ollama.com/library/qwen2.5:0.5b) · [Qwen2.5 1.5B](https://ollama.com/library/qwen2.5:1.5b) · [Qwen3 1.7B](https://ollama.com/library/qwen3:1.7b)

Pred opravou vyhľadávanie pri `71/1967 § 54 ods. 1; ods. 2` poskytlo jeden z dvoch odsekov. Po oprave oba odseky prešli do kontextu a záchyt všetkých očakávaných referencií stúpol z 3/4 na 4/4. V prvom behu boli tiež všetky tri nové exporty a medzi snímkami sa doplnilo označenie § 82 ako prechodného ustanovenia, ktoré otázky nepoužívali.

Qwen2.5 1.5B v odpovedi na otázku o odvolaní spojil informáciu o orgáne, lehote a výnimke z oboch odsekov. V tomto porovnaní chýbali platné citačné značky. Qwen2.5 1.5B a Qwen3 vytvorili tri značky `[[S1]]` pri otázkach bez podkladov. Server všetky odmietol. Pri otázke o otcovstve Qwen3 doplnil aj nesprávne číslo predpisu v obyčajnom texte. Správnosť a úplnosť odpovedí čakajú na odborný posudok.

## Kontrolný beh s upraveným validátorom

Starší výstup Qwen2.5 0.5B obsahoval presný identifikátor ústavného odseku v jednoduchých hranatých zátvorkách. Pri opätovnom spracovaní tejto odpovede opravený validátor priradil odkaz k úseku z kontextu a pri prázdnom kontexte ho odmietol. Prompt už neposkytuje pevný príklad značky. Model dostáva značky ako `[S1]` iba pri skutočne vložených zdrojoch.

| Model, `mmap` vypnuté | Dokončené | Medián času | Medián tok/s | Špička PSS | Očakávané citácie | Dĺžkový limit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5 0.5B Q4_K_M | 5/5 | 9,83 s | 28,41 | 592 MiB | 0/4 | 1/5 |
| Qwen2.5 1.5B Q4_K_M | 5/5 | 25,16 s | 16,90 | 1 217 MiB | 0/4 | 1/5 |

Oba modely dostali všetky štyri očakávané pasáže do kontextu. V tomto behu modely nevytvorili žiadnu značku, ktorú by validátor prijal alebo odmietol. Úlohy mimo pokrytia zostali bez zdrojov. Na zaslepené hodnotenie sa pripravilo 15 odpovedí, po päť od každého modelu. Požadované právne posudky ostávajú nevyplnené.

## Pamäť a nastavenie mapovania

Kontrolné meranie zopakovalo prvú otázku výhradne s Qwen2.5 1.5B. Pri `--mmap` bolo spoločné PSS 1 811 MiB a latencia 25,20 s. Pri `--no-mmap` bolo približne 1 211 MiB a latencia 25,40 s. Odpoveď bola rovnaká. Ide o jedno meranie na režim. Ďalší beh použil vypnuté mapovanie.

Päťotázkové porovnanie modelov Qwen2.5 využívalo priemerne 49,9 % kvóty CPU. Najvyššie namerané `memory.current` bolo 3 112 MiB vrátane súborovej cache. Po odpočítaní `inactive_file` dosiahla pracovná sada 2 384 MiB, približne 58 % limitu cgroup. Qwen3 využíval priemerne 53,0 % CPU kvóty a dosiahol pracovnú sadu 2 290 MiB. Pri načítaní Qwen3 dosiahla celková účtovaná pamäť vrátane cache limit 4 GiB a cgroup zaznamenala reclaim. Zaznamenaný swap a OOM zostali na nule. Po každej sérii bol zoznam načítaných modelov prázdny.

Kontrolný beh oboch Qwen2.5 s vypnutým mapovaním využíval priemerne 51,5 % kvóty CPU. `memory.current` dosiahla 3 480 MiB a pracovná sada 1 658 MiB. Odlišné množstvo súborovej cache vysvetľuje, prečo špička `memory.current` môže stúpnuť aj pri menšej pracovnej sade a menšom PSS.

## Reprodukcia a príprava dát

Na lokálnom serveri s dvomi nainštalovanými modelmi a importovaným korpusom možno zopakovať päťotázkový kontrolný beh. [Postup importu](LEGAL_CORPUS_STATUS.md)

```sh
uv run --locked python -m scripts.benchmark \
  --cases benchmarks/slovak-cloud-law.jsonl --data-dir .tm-law/slovlex \
  --require-source-audit --model qwen2.5:0.5b --model qwen2.5:1.5b \
  --device cpu --num-threads 1 --context-window 2048 --max-tokens 160 \
  --temperature 0 --seed 42 --no-mmap --measure-memory --summary \
  --output .tm-law/cloud-benchmark.json
```

Preflight reálneho LoRA alebo QLoRA vyžaduje aktuálnu cloudovú sadu ako tretí holdout. Skúška prípravy dát vytvorila osem syntetických tréningových, jeden validačný a jeden testovací záznam. Odborné posudky a licencované právne tréningové odpovede treba doplniť pred adaptáciou skutočného modelu. [Príprava tréningu](TRAINING.md)

## Projektové kontroly

Prešli Ruff lint a kontrola formátovania, 69 testov Pythonu, TypeScript, produkčný build a štyri testy histórie frontendu. Dve podmienené kontroly základnej sady pytest boli preskočené. Ide o Windows CIM a opt-in test Ollamy. Prešiel aj mock benchmark 3/3, syntetický import, audit ôsmich referencií zákona o rodine, všetkých 14 vyhľadávacích prípadov z dvoch právnych sád a príprava dát s tromi holdoutmi. Bežiaci FastAPI server sprístupnil produkčný frontend a mock chat vložil oba požadované odseky do kontextu.
