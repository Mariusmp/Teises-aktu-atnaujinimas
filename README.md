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

## Ekrano kopijos
Standartinis veikimas, kai jau dalis PDF yra diske:

<img width="1245" height="422" alt="image" src="https://github.com/user-attachments/assets/b95a4af6-d9af-46e3-b6dd-efd3cf2f1154" />

Kai nuoroda yra ne PDF failas:

<img width="1631" height="63" alt="image" src="https://github.com/user-attachments/assets/7a16b397-89b3-4588-baec-bbb12294f20c" />

Kai aktuali versija nesutampa su esančia diske:

<img width="595" height="95" alt="image" src="https://github.com/user-attachments/assets/366e0261-50bd-43f5-aef7-134daacdb7cf" />

Rastos naujos nuorodos faile, kurios dar nėra atsiųstos į diską:

<img width="871" height="234" alt="image" src="https://github.com/user-attachments/assets/15064ef0-8e2d-4e2c-bab8-bb3cf1d362ad" />
