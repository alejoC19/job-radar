# job-radar

Bot en Python que busca avisos de trabajo en Argentina, los puntúa contra
3 perfiles de CV y manda un resumen diario por Telegram. No se postula
automáticamente: solo filtra y avisa.

## Estado actual

- [x] Workflow de prueba de Telegram (`.github/workflows/job-radar-test.yml`)
- [x] Scoring de avisos contra los 3 perfiles + tests (`job_radar/scoring.py`)
- [x] Extracción de sueldo por regex (`job_radar/salary.py`)
- [x] Dedup de avisos ya vistos (`job_radar/dedup.py`)
- [x] Export a Excel con una hoja por perfil (`job_radar/export.py`)
- [x] Envío del mensaje diario + Excel adjunto por Telegram (`job_radar/notifier.py`, `job_radar/main.py`)
- [x] Scraper de Computrabajo Argentina (`job_radar/sources/computrabajo.py`):
      parsea el HTML de busqueda (`ar.computrabajo.com/trabajo-de-{keyword}`,
      no hay API publica)
- [x] Scraper de Bumeran Argentina (`job_radar/sources/bumeran.py`): el sitio
      es una SPA de React sin HTML util, pero el frontend llama a una API
      JSON interna (`POST /api/avisos/searchV2` con header `x-site-id: BMAR`)
      que se consume directo con `requests`
- [ ] Workflow con cron (9 y 18 hs Argentina)

Fuentes: se descartó Get on Board (no lo usa el dueño del proyecto) y
LinkedIn (su `robots.txt` prohíbe rastrear resultados de búsqueda de
empleo y su ToS prohíbe el scraping). Se usan Computrabajo Argentina y
Bumeran, con la misma interfaz intercambiable para sumar más después.

Ambos scrapers buscan por un set fijo de terminos que cubre los 3 perfiles
(`SEARCH_TERMS` en `job_radar/sources/base.py`: "qa automation", "tester",
"desarrollador", "analista contable"), paginan hasta `max_pages` (2 por
default) y dedupean por URL. El scoring de `job_radar/scoring.py` es el que
despues decide, aviso por aviso, si es relevante para cada perfil.

## Setup local

```bash
pip install -r requirements.txt
cp .env.example .env   # completar con tus valores, nunca commitear .env
pytest -v
```

## Configuración de GitHub Secrets

Este repo necesita, en Settings → Secrets and variables → Actions →
**Repository secrets**:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Arquitectura

Ver `job_radar/` para el paquete Python. Cada fuente de avisos implementa
la interfaz `Scraper` de `job_radar/sources/base.py` (un `fetch()` que
devuelve `list[JobListing]`), para poder sumar sitios nuevos sin tocar el
resto del código.
