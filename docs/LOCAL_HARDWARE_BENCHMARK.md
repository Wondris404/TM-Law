# Lokálny hardvér a merania TM-Law

**Stav merania na cieľovom Lenovo s Windows 11 je Blocked.** V tomto behu bol dostupný iba vzdialený linuxový server. Deklarovaný Ryzen 7 7730U, grafika Radeon a 16 GB RAM sú údaje zo zadania. Miestny klon, konfigurácia Windows, využitie diskov a pamäte, Ollama a Vulkan na Lenovo čakajú na systémové overenie.

Na cieľovom počítači spustite inventár z koreňa existujúceho klonu:

```powershell
.\scripts\diagnose-windows.ps1
```

Výstup sa uloží do ignorovaného adresára `.tm-law/hardware/`. Skript zisťuje verzie nástrojov a stav existujúcej Ollamy na loopback. Zobrazuje momentálne nainštalované a načítané modely. Nenahrádza kontrolu konfigurácie bežiacej služby. Nález knižnice Vulkan potvrdzuje prítomnosť loadera, úspešnú akceleráciu treba zmerať. Inventár nespúšťa server, nenačítava modely a nič nesťahuje.

| Model | Kontexty | Uvažovanie | Stav merania |
| --- | --- | --- | --- |
| `qwen3.5:4b` | 2048, 4096, 8192 podľa rezervy | Auto, off/on podľa podpory | Čaká na cieľový počítač |
| `qwen3.5:9b` | 2048, 4096, 8192 podľa rezervy | Auto, off/on podľa podpory | Čaká na cieľový počítač a kontrolu veľkosti váh |
| `abliterant/qwen3.5-rana:9b` | 2048, 4096, 8192 podľa rezervy | Auto, off/on podľa podpory | Čaká na cieľový počítač a kontrolu veľkosti váh |

Kvantizácia, čas načítania, prvý token, latencia, dĺžka odpovede, tok/s, úspešnosť, stabilita a RAM pre tieto tagy ešte nemajú namerané hodnoty. Merania malého syntetického modelu sú evidované samostatne v [dôkazoch v0.1.2](PERFORMANCE_v0.1.2.md).

Prvá skúšobná konfigurácia pre 16 GB RAM je `qwen3.5:4b`, kontext 2 048, jeden model a CPU. Merajte jednu kombináciu naraz podľa [Windows postupu](WINDOWS_SETUP.md). Spolu s latenciou a rýchlosťou sledujte fyzickú pamäť systému, RSS a USS procesov. Spoločný PSS nemusí byť dostupný na Windows. Ollamou hlásenú VRAM a veľkosť váh na disku uvádzajte samostatne. Limit 12 GB pre aplikáciu a inferenciu treba overiť meraním so zachovaním rezervy systému. Surové výstupy patria do `.tm-law/`.

## Samostatné reálne meranie na Linuxe

Meranie z 19. novembra 2026 použilo Ollamu 0.40.16 a oficiálny tag [`qwen3.5:2b-q4_K_M`](https://ollama.com/library/qwen3.5:2b-q4_K_M) s digestom `1e2d21a4f03ab9e4a9c1976a4b7e88f21de61d65f2c5485d8fde8942be73f1e7`. Ollama evidovala model ako 1,9B a jeho záznam na disku mal 1 945 781 358 bajtov. Hostiteľ používal AMD EPYC, kvótu dvoch CPU a cgroup limit 4 GiB. Inferencia bežala na CPU s dvoma vláknami, na loopbacku, s vypnutými cloudovými funkciami a s jedným načítaným modelom.

Prvý pokus s predvolenými 16 vláknami prekročil 160-sekundový limit. Po nastavení dvoch vlákien prišiel v krátkej kontrolnej požiadavke bez uvažovania prvý token za 3,83 s. Studené načítanie trvalo 3,40 s. V plnom chate TM-Law nad historickým znením Ústavy prišiel prvý token za 10,38 s, celá požiadavka trvala 15,60 s a generovanie dosiahlo 18,38 tok/s. Aplikácia overila očakávaný identifikátor článku. Beh dosiahol limit 96 generovaných tokenov.

### Výkon cez štandardný benchmark

Pri každej konfigurácii sa použila rovnaká kontrolná otázka s teplotou 0, seedom 42 a rozpočtom 192 generovaných tokenov. `keep_alive=0` vyžiadal uvoľnenie modelu po požiadavke. Pri zapnutom uvažovaní je prvá udalosť interným signálom uvažovania. Výsledok neobsahoval viditeľný token odpovede.

| Kontext | Uvažovanie | Načítanie s | Prvý token s | Latencia s | Tok/s | Spoločná PSS MiB | Výsledok |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2048 | off | 3,16 | 8,73 | 18,86 | 18,96 | 2 171 | Viditeľná odpoveď, limit 192 |
| 2048 | on | 2,93 | 8,48 | 18,41 | 19,34 | 2 173 | Iba uvažovanie, limit 192 |
| 4096 | off | 2,96 | 8,23 | 18,18 | 19,29 | 2 199 | Viditeľná odpoveď, limit 192 |
| 4096 | on | 2,91 | 8,38 | 18,24 | 19,46 | 2 198 | Iba uvažovanie, limit 192 |

Spoločná PSS je špička simultánnej vzorky aplikácie a detegovaných procesov Ollamy. Veľkosť váh na disku, RSS a hranica kontajnera sú samostatné údaje. V meraní nevznikla udalosť OOM. Kontext 8192 sa v tomto behu nemeral.

Na deviatich prípadoch zákona o rodine pri 2048 tokenoch a vypnutom uvažovaní dokončil model 9/9 odpovedí. Všetky dosiahli limit dĺžky. Audit a vyhľadávanie našli všetkých 8 očakávaných prameňov. Model správne uviedol očakávaný identifikátor v 4 z 8 prípadov a pri kontrole mimo dátumového pokrytia citáciu nevytvoril. Medián bol 20,34 s, 19,36 tok/s a prvý token po 10,37 s. Špička PSS bola približne 2 199 MiB. Odborné hodnotenie právnej správnosti zatiaľ chýba.

```sh
uv run --locked python -m scripts.benchmark --model qwen3.5:2b-q4_K_M --device cpu --num-threads 2 --temperature 0 --context-window 2048 --context-window 4096 --reasoning off --reasoning on --max-tokens 192 --measure-memory --summary
```

Tieto hodnoty platia pre uvedený Linux. Merania na Lenovo, väčšie Qwen modely a úspešná odpoveď so zapnutým uvažovaním po zvýšení rozpočtu tokenov zostávajú otvorené.
