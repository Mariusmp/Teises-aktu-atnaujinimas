# Teisės Aktų Atnaujinimo Scenarijus

Tai yra Python scenarijus, skirtas automatizuotam teisės aktų pakeitimų sekimui, atsisiuntimui į asmeninį Google Drive.

## Apie Projektą

Šis projektas buvo sukurtas siekiant automatizuoti periodiškai pasikartojantį procesą: atsisiųsti naujausias teisės aktų redakcijas iš nurodytų URL, palyginti jas su senomis versijomis ir pateikti pakeitimų ataskaitą. Vėliau tokį failų rinkinį patogu naudoti apmokant AI atsakyti į teisinius klausimus, nes AI sunkiai supranta, kokia yra aktuali teisės akto redakcija.

## Funkcionalumas

* Skaito teisės aktų pavadinimus ir nuorodas iš Google Sheets failo.
* Atsisiunčia naujausias redakcijas ir išsaugo jas PDF formatu Google Drive aplanke.
* Automatiškai konvertuoja HTML, ODT, DOCX formatus į PDF.
* Palygina naujos ir senos redakcijos tekstus ir informuoja apie pakeitimus.
* Yra valdomas per terminalą arba paspaudus darbalaukio ikoną.

## Naudotos technologijos

* Python 3
* Google Drive API
* Google Sheets API
* Playwright (HTML -> PDF konvertavimui)
* ir kitos Python bibliotekos.
