# Bezpečnosť a súkromie

Spúšťajte backend aj Ollamu na loopback adrese. TM-Law odmieta neznáme hodnoty Host, cudzí Origin a požiadavky označené prehliadačom ako cross-site. Aplikácia neobsahuje telemetriu, automatický externý upload ani vzdialenú zálohu inferencie. Kliknutie na pôvodný zdroj otvorí externú stránku v novej karte. Ďalšie programy alebo používatelia s prístupom k lokálnemu portu alebo súborom predstavujú samostatný predpoklad dôvery. MVP nemá prihlasovanie.

Nahraté súbory sa pred spracovaním kontrolujú podľa veľkosti a podporovaného typu. Extrakcia prebieha v samostatnom procese s časovým limitom. DOCX sa rozbaľuje iba v pamäti, bez vykonávania makier, spracovania externých vzťahov či použitia názvu súboru ako cesty. Limit podprocesu nie je izolácia na úrovni OS. PDF a DOCX treba ďalej testovať na škodlivé vstupy a zvážiť izoláciu procesu s pamäťovým limitom. Aplikácia dosahuje iba základnú ochranu proti prompt injection. Model nemá nástroje na vykonávanie príkazov ani sieťové volania a obsah zdrojov sa vkladajú ako dáta pod oddelený systémový pokyn. Pokyn nedokáže zabrániť všetkým zavádzajúcim odpovediam.

Dokumentový index, história prehliadača a odpovede sú **bez aplikačného šifrovania**. Odstránenie dokumentu vymaže záznam z aplikačného zoznamu, ale nezaručuje vymazanie uložených odpovedí, záloh, dočasných súborov alebo zvyškov na disku. História zobrazená v chate sa maže samostatne. Pred prácou s advokátskym spisom overte ochranu zariadenia, prístup k profilu prehliadača a režim zálohovania.

Pre kancelárske nasadenie treba zaviesť riadenie prístupu a životného cyklu dokumentov, šifrovanie a správu kľúčov, zdokumentované vymazávanie a kontrolu záloh. Dodržiavanie GDPR a advokátskej mlčanlivosti závisí od procesov kancelárie a od spôsobu nasadenia. Testy MVP túto zhodu nepotvrdzujú.

Odstránenie súkromného dokumentu používa režim SQLite `secure_delete` pre aktívnu databázu. Prehliadač, pracovný adresár, diskové snímky, zálohy a samotné úložisko môžu uchovať kópie. K úplnému vymazaniu ani k šifrovaniu sa toto nastavenie nevzťahuje. Import zložiek právneho korpusu je offline a XML/HTML sa spracúva ako text bez externého načítania.
