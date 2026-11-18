# Modely

MVP posiela streamované požiadavky na lokálne Ollama API. Zoznam dostupných modelov zisťuje v Ollame. Model sa vyberá v rozhraní alebo cez `TM_LAW_MODEL`. Kvantizáciu určuje nainštalovaný modelový tag alebo vlastný lokálny model. Nastavenia kontextu, teploty a limitu odpovede odosiela aplikácia pri otázke. Aplikácia nezisťuje výkon z deklarovanej kvantizácie.

| Model na porovnanie | Tag |
| --- | --- |
| RANA 9B, experimentálny predvolený tag | `abliterant/qwen3.5-rana:9b` |
| Qwen3.5 9B | `qwen3.5:9b` |
| Qwen3.5 4B, vhodný prvý pokus na CPU | `qwen3.5:4b` |

Modelové karty a distribúcia: [RANA](https://huggingface.co/abliterant/Qwen3.5-9B-RANA-abliterated), [RANA GGUF](https://huggingface.co/abliterant/Qwen3.5-9B-RANA-abliterated-GGUF), [Ollama RANA](https://ollama.com/abliterant/qwen3.5-rana), [Ollama Qwen3.5](https://ollama.com/library/qwen3.5).

## Uvažovanie

- **Auto** ponechá rozhodnutie na modeli a žiadosť neobsahuje parameter `think`.
- **Zapnuté** používa `true` alebo jednu z podporovaných pomenovaných úrovní z `/api/show`.
- **Vypnuté** vyžaduje potvrdenú podporu `false`. Modely s povinným uvažovaním dostanú hlásenie o kompatibilite a žiadosť sa nevygeneruje. Pri starších verziách so známou rodinou a deklarovanou schopnosťou uvažovania je k dispozícii obmedzená kompatibilita.

Interný text z poľa `message.thinking` ani rozpoznané bloky `<think>` sa neodosielajú do prehliadača, necitujú sa a neukladajú sa do benchmarku. Používateľ vidí iba stav uvažovania a prípadne metriky. Nie každý model používa rovnakú schému alebo vie uvažovanie naozaj vypnúť. Pri nejasnej podpore použite **Auto** a zmerajte správanie modelu na cieľovom hardvéri. [Ollama Thinking](https://docs.ollama.com/capabilities/thinking).

Po stiahnutí váh používajte Ollamu s vypnutými cloudovými funkciami podľa [oficiálneho postupu](https://docs.ollama.com/faq#how-do-i-disable-ollama-s-cloud-features). Aplikácia používa loopback, neberie proxy z prostredia a vynecháva identifikované cloudové modely. Ollama beží ako samostatný program a jej konfiguráciu spravuje používateľ.

Právnu presnosť, spoľahlivosť a mieru neopodstatnených odmietnutí treba merať na rovnakých odborne overených zadaniach. Zmena alignmentu nepredpovedá kvalitu. Cieľ pre notebook je do 12 GB celkovej pamäte pre aplikáciu a inferenciu. Začnite s kvantizovaným 4B modelom, kontextom 2 048 až 4 096 tokenov a jednou požiadavkou naraz. Zapnite meranie procesov v nastaveniach a skontrolujte aj pamäť systému v Správcovi úloh; testy v Linuxe nepotvrdzujú latenciu ani RAM na Ryzen 7 7730U. Reálna inferencia, licencia konkrétneho balíka váh a výkon týchto troch modelov zatiaľ neboli overené v tomto behu.
