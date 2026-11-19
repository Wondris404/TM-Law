# Webová rešerš v TM-Law

V chate zapnite **Webová rešerš**. Právnu alebo ekonomickú otázku napíšte do hlavného poľa. Do oddeleného poľa **Verejný dopyt** zadajte to, čo môže opustiť počítač. Webovú rešerš má každá otázka vypnutú, kým ju výslovne nezapnete.

| Verejný dopyt | Čo aplikácia urobí |
| --- | --- |
| IČO, napríklad **IČO 31320155** | Načíta výsledky z Obchodného registra, vyhľadanie v RPO a metadáta účtovnej jednotky v RÚZ. Pri jedinom výsledku v Obchodnom registri skúsi otvoriť aj aktuálny výpis. Beží aj bez API kľúča. |
| HTTPS odkaz na podporovaný verejný portál | Otvorí priamo stránku alebo PDF s textovou vrstvou. Vyberie úryvok podľa otázky. Beží aj bez API kľúča. |
| Téma, napríklad **HICP Slovensko medziročná inflácia Eurostat** | Vyhľadá stránky cez Brave Search podľa zvolenej oblasti. Prečíta až šesť dostupných stránok na podporovaných doménach a vyberie úryvky. Vyžaduje kľúč Brave Search API. |
| Všeobecná téma, napríklad **tepelné čerpadlá v zime; porovnanie prevádzkových nákladov** | Vyberte **Celý web · viac krokov**. Aplikácia začne dopytom na celú tému a podľa podkladov vyhľadá nepokryté podtémy alebo ďalšiu doménu. Urobí najviac tri dopyty a uprednostní rôzne vydavateľské domény pri výbere najviac šiestich podkladov. Obsah číta z indexu Brave LLM Context a cituje pôvodné adresy. |

## Nastavenie textového vyhľadávania

Pred štartom nastavte v prostredí backendu **TM_LAW_BRAVE_SEARCH_API_KEY** na vlastný kľúč [Brave Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started). Režim **Celý web · viac krokov** vyžaduje prístup k [Brave LLM Context](https://api-dashboard.search.brave.com/documentation/services/llm-context). Kľúč ostáva na backende. Rozhranie zobrazuje iba informáciu, či je nakonfigurovaný. Po zmene hodnoty reštartujte backend.

Právna otázka, dátum, nahraté dokumenty a generovanie odpovede sa spracúvajú lokálne. Externé požiadavky používajú verejný dopyt, jeho spresnenia, odvodený identifikátor, zvolenú adresu alebo výsledok vyhľadávača. Preto do verejného dopytu vkladajte výhradne verejné informácie. Pri priamom sťahovaní sa používajú podporované HTTPS domény, obmedzené presmerovania, najviac 4 MiB na odpoveď a PDF v rámci limitov existujúceho extraktora. Pri odkaze mimo podporovaných domén režim celého webu použije text z indexu iba vtedy, keď ho dostane k presnej adrese.

## Ako čítať výsledok

Citácie smerujú k pôvodnej stránke alebo záznamu a karta ukazuje text použitý v kontexte. Pri celom webe karta označí úryvok z indexu a uvedie čas načítania do indexu, ak ho Brave poskytne. Tento čas označuje získanie obsahu indexom. Rozhodujúci dátum filtruje lokálny korpus. Pri webovom podklade sa použiteľná časová verzia posudzuje podľa obsahu zdroja. Webové úryvky sa automaticky nepridávajú do právnej databázy.

Výsledky režimu **Celý web · viac krokov** sú k dispozícii počas aktuálnej relácie karty. Dlhodobé ukladanie výsledkov Brave vyžaduje plán s právami na ukladanie. [Podmienky Brave Search API](https://brave.com/search/api/)

Základný konektor RÚZ číta identitu účtovnej jednotky a evidenciu dokumentov. Na analýzu tržieb, záväzkov alebo iných súm otvorte konkrétny výkaz a zadajte odkaz na čitateľnú verejnú prílohu. Portál vyžadujúci prihlásenie, vykonanie JavaScriptu, OCR alebo neprístupný z danej siete môže vyžadovať otvorenie v prehliadači. Aplikácia pri takom výsledku uvedie medzeru a použije ostatné dostupné podklady.

V Codexe je plný postup dostupný cez [$web-research](../.agents/skills/web-research/SKILL.md) s nástrojmi webového vyhľadávania dostupnými v danej relácii.
