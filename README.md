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
- [ ] Scrapers reales: Computrabajo Argentina + Bumeran (interfaz lista en
      `job_radar/sources/`, bloqueado por acceso de red del entorno de dev —
      ver más abajo)
- [ ] Workflow con cron (9 y 18 hs Argentina)

Fuentes: se descartó Get on Board (no lo usa el dueño del proyecto) y
LinkedIn (su `robots.txt` prohíbe rastrear resultados de búsqueda de
empleo y su ToS prohíbe el scraping). Se usan Computrabajo Argentina y
Bumeran, con la misma interfaz intercambiable para sumar más después.

### Bloqueo de red en desarrollo

El entorno donde se desarrolla este proyecto no tiene salida a
`computrabajo.com.ar` ni `bumeran.com.ar`, así que los scrapers reales
todavía no se escribieron contra HTML real. Para destrabar: ampliar el
acceso de red del entorno, o pasar HTML de ejemplo de un par de avisos de
cada sitio para armar el parser y los fixtures de test sobre eso.

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
la interfaz de `job_radar/sources/base.py` (cuando exista), para poder
sumar sitios nuevos sin tocar el resto del código.
