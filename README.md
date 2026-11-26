# Teisės Aktų Atnaujinimo Sistema

Automatizuota žiniatinklio aplikacija ir Docker konteineris, skirtas teisės aktų pakeitimų sekimui, atsisiuntimui į Google Drive (`.pdf` ir `.md` formatais) bei versijų palyginimui.

## Apie projektą

Sistema automatizuoja periodinį teisės aktų suvestinių redakcijų tikrinimą pagal Google Sheets sąrašą. Kiekvienam dokumentui Google Drive aplanke sukuriami du failai: pilnas daugiapuslapis `.pdf` ir nuo navigacijos bei meniu išvalytas `.md` (Markdown) failas. Švarūs `.md` failai pritaikyti RAG sistemoms (pvz., Open WebUI žinių bazėms), kad kalbos modeliai remtųsi tik aktualia teisės akto redakcija.

## Funkcionalumas

- **Duomenų šaltinis:** skaito teisės aktų pavadinimus ir URL nuorodas iš Google Sheets (`RANGE_NAME`).
- **3 pakopų dokumentų gavimas (Playwright):**
  1. Pirmiausia perima tikrą daugiapuslapį `.pdf` failą tiesiai iš puslapio mygtuko (pvz., `e-tar.lt`).
  2. Jei PDF nėra, atsisiunčia `.docx` arba `.odt` ir konvertuoja į `.pdf` per Google Drive API.
  3. Jei atsisiuntimo mygtukų nėra, pritaiko spausdinimo CSS ir sugeneruoja pilną daugiapuslapį HTML → PDF dokumentą.
- **Švarus Markdown (`.md`) eksportas:** iškerpa pagrindinį akto tekstą iš HTML, `.docx` arba `.pdf` ir išsaugo jį tame pačiame Google Drive aplanke.
- **WAF ir blokavimų apsauga:** atpažįsta Cloudflare blokavimo puslapius bei tuščius AWS WAF (EUR-Lex) atsakus, todėl neperrašo gerų failų tuščiais; ES reglamentams naudoja atsarginį atsisiuntimą per Playwright naršyklę.
- **Versijų palyginimas (Diff):** lygina naują ir seną `.md` redakcijas (`diff-match-patch`) ir WebUI sąsajoje parodo vizualią pakeitimų ataskaitą.
- **WebUI ir valdymas realiuoju laiku:** apsaugota prisijungimu (`HTTP Basic Auth`), rodo progreso juostą, tiesioginį proceso žurnalą per WebSocket ir leidžia bet kada sustabdyti vykdymą mygtuku **Sustabdyti**.
- **Automatinis tvarkaraštis:** periodinis paleidimas pagal CRON nustatymus (`APScheduler`).

## Naudotos technologijos

- **Backend:** Python 3.12, FastAPI, Uvicorn, WebSockets, APScheduler
- **Naršyklės automatizacija ir teksto apdorojimas:** Playwright (Chromium), BeautifulSoup4, Markdownify, python-docx, PyPDF2, diff-match-patch
- **Integracijos ir diegimas:** Google Drive API, Google Sheets API, Docker, GitHub Actions (CI/CD į GHCR)

## Konfigūracija ir paleidimas (Docker)

Konteineriui būtini Google Cloud OAuth failai (`credentials.json` ir `token.json`) bei aplinkos kintamieji:

| Kintamasis | Paskirtis | Pavyzdys |
| :--- | :--- | :--- |
| `APP_PASSWORD` | Privalomas. WebUI slaptažodis (vartotojas: `admin`) | `slaptazodis` |
| `SPREADSHEET_ID` | Privalomas. Google Sheets dokumento ID | `1n1I8lf...` |
| `DRIVE_FOLDER_ID` | Privalomas. Tikslinio Google Drive aplanko ID | `1G17TuD...` |
| `RANGE_NAME` | Lentelės lapas ir stulpelių intervalas | `Sheet1!A:B` |
| `CRON_DAY` | Mėnesio diena automatiniam paleidimui | `1` |
| `CRON_HOUR` | Valanda automatiniam paleidimui | `9` |
| `CRON_MINUTE` | Minutė automatiniam paleidimui | `0` |

```bash
docker run -d \
  --name="ta-update" \
  --restart unless-stopped \
  -p 8000:8000 \
  -e APP_PASSWORD="<slaptazodis>" \
  -e SPREADSHEET_ID="<google_sheets_id>" \
  -e DRIVE_FOLDER_ID="<google_drive_folder_id>" \
  -e CRON_DAY="1" \
  -e CRON_HOUR="9" \
  -e CRON_MINUTE="0" \
  -v /path/to/credentials.json:/app/credentials.json:ro \
  -v /path/to/token.json:/app/token.json:rw \
  ghcr.io/mariusmp/teises-aktu-atnaujinimas:main
```
# Ekrano kopijos
<img width="1063" height="577" alt="image" src="https://github.com/user-attachments/assets/3e908564-8ece-4e26-8621-49def2634280" />

