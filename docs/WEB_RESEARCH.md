# Webová rešerš v TM-Law

V chate zapnite **Webová rešerš**. Právnu alebo ekonomickú otázku napíšte do hlavného poľa. Do oddeleného poľa **Verejný dopyt** zadajte to, čo môže opustiť počítač. Webovú rešerš má každá otázka vypnutú, kým ju výslovne nezapnete.

| Verejný dopyt | Čo aplikácia urobí |
| --- | --- |
| IČO, napríklad **IČO 31320155** | Načíta výsledky z Obchodného registra, vyhľadanie v RPO a metadáta účtovnej jednotky v RÚZ. Pri jedinom výsledku v Obchodnom registri skúsi otvoriť aj aktuálny výpis. Beží aj bez API kľúča. |
| HTTPS odkaz na podporovaný verejný portál | Otvorí priamo stránku alebo PDF s textovou vrstvou. Vyberie úryvok podľa otázky. Beží aj bez API kľúča. |
| Téma, napríklad **HICP Slovensko medziročná inflácia Eurostat** | Vyhľadá stránky cez Brave Search podľa zvolenej oblasti. Prečíta až šesť dostupných stránok na podporovaných doménach a vyberie úryvky. Vyžaduje kľúč Brave Search API. |

## Nastavenie textového vyhľadávania

Pred štartom nastavte v prostredí backendu **TM_LAW_BRAVE_SEARCH_API_KEY** na vlastný kľúč [Brave Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started). Kľúč ostáva na backende. Rozhranie zobrazuje iba informáciu, či je nakonfigurovaný. Po zmene hodnoty reštartujte backend.

Právna otázka, dátum, nahraté dokumenty a generovanie odpovede sa spracúvajú lokálne. Externé požiadavky používajú verejný dopyt, odvodený identifikátor, zvolenú adresu alebo výsledok vyhľadávača. Preto do verejného dopytu vkladajte výhradne verejné informácie. Vyhľadávanie pracuje s existujúcimi verejnými stránkami a API. Podporuje HTTPS, obmedzené presmerovania, najviac 4 MiB na odpoveď a PDF v rámci limitov existujúceho extraktora.

## Ako čítať výsledok

Citácie smerujú k načítanej stránke alebo záznamu a karta ukazuje úryvok aj čas získania. Vyhľadávací úryvok sa ako dôkaz nepoužíva. Rozhodujúci dátum filtruje lokálny korpus. Pri živom webovom podklade sa použiteľná časová verzia posudzuje podľa obsahu zdroja. Webové úryvky sa automaticky nepridávajú do právnej databázy.

Základný konektor RÚZ číta identitu účtovnej jednotky a evidenciu dokumentov. Na analýzu tržieb, záväzkov alebo iných súm otvorte konkrétny výkaz a zadajte odkaz na čitateľnú verejnú prílohu. Portál vyžadujúci prihlásenie, vykonanie JavaScriptu, OCR alebo neprístupný z danej siete môže vyžadovať otvorenie v prehliadači. Aplikácia pri takom výsledku uvedie medzeru a použije ostatné dostupné podklady.

V Codexe je plný postup dostupný cez [$web-research](../.agents/skills/web-research/SKILL.md) s nástrojmi webového vyhľadávania dostupnými v danej relácii.
