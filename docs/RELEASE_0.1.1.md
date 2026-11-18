# Technické poznámky k v0.1.1

- Benchmark zapisuje UTF‑8 aj pri nekompatibilnom predvolenom kódovaní Windows konzoly. CI nastavuje UTF‑8 a test cielene spúšťa podproces s `cp1252`.
- Rozhranie a Ollama adaptér podporujú Auto, zapnuté a vypnuté uvažovanie podľa možností modelu. Súkromné uvažovanie sa nezobrazuje v odpovedi. Citácie sa kontrolujú až z viditeľnej odpovede.
- Benchmarker porovnáva lokálne modely nad rovnakou snímkou korpusu, podporuje opakovania, kontexty a metriky času, tokenov a pamäte. Pribalená reálna diagnostická úloha posudzuje dostupnosť a výkon runtime bez právneho korpusu. Právne hodnotenie vyžaduje overený korpus a odbornú kontrolu.
- Rôzne verzie rovnakého právneho úseku sú označené a pri nedostatku dôkazov dostane používateľ výslovné upozornenie. Overený identifikátor potvrdzuje väzbu na pasáž, nie právnu správnosť záveru.
- Windows spúšťač používa pripravené závislosti, overí lokálny backend a frontend a v bežnom režime skontroluje Ollamu a model. CI obsahuje samostatnú skúšku spúšťača s testovacím adaptérom.

Automatizované lokálne testy používajú testovací adaptér alebo emuláciu protokolu Ollama cez loopback. Skutočná inferencia s váhami, offline skúška a meranie RAM na Lenovo 82XY vyžadujú cieľové zariadenie. Aplikačné šifrovanie a overený slovenský právny korpus zostávajú mimo tejto verzie. [Windows](WINDOWS_SETUP.md) · [Benchmarky](BENCHMARKS.md) · [Bezpečnosť](SECURITY.md)
