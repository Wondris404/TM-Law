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
