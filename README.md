# job-radar

Bot en Python que busca avisos de trabajo en Argentina, los puntúa contra
3 perfiles de CV y manda un resumen diario por Telegram. No se postula
automáticamente: solo filtra y avisa.

## Estado actual

- [x] Workflow de prueba de Telegram (`.github/workflows/job-radar-test.yml`)
- [x] Scoring de avisos contra los 3 perfiles + tests (`job_radar/scoring.py`)
- [ ] Scrapers (Get on Board, Computrabajo)
- [ ] Dedup de avisos ya vistos
- [ ] Armado y envío del mensaje diario
- [ ] Workflow con cron (9 y 18 hs Argentina)

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
