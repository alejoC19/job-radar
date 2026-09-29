# job-radar

Bot en Python que busca avisos de trabajo en Argentina y los puntúa contra
perfiles de CV. No se postula automáticamente: solo filtra y avisa.

Dos formas de usarlo:
- **Bot de Telegram** (`job_radar/`): corre solo 2 veces por día contra 3
  perfiles fijos definidos en `config.yaml`, manda el resumen por Telegram.
- **Sitio web** (`api/` + `web/`): login, perfiles de CV propios editables
  desde la web, botón para generar el Excel al toque en vez de esperar la
  corrida de Telegram. Ver la sección "Sitio web" más abajo.

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
- [x] Workflow con cron (9 y 18 hs Argentina, `.github/workflows/job-radar-cron.yml`)
- [x] Sitio web con login y perfiles de CV propios por usuario (`api/`,
      `web/`, `supabase/migrations/`), ver sección "Sitio web"

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

## Corrida automática

`.github/workflows/job-radar-cron.yml` corre el bot todos los días a las
9 y 18 hs de Argentina (`cron: "0 12,21 * * *"`, UTC-3 fijo todo el año) y
también se puede disparar a mano desde Actions → Job Radar - Corrida diaria
→ Run workflow.

Como los runners de GitHub Actions son efímeros, `data/seen.json` (los
avisos ya notificados) se versiona en el repo: el workflow lo commitea de
vuelta después de cada corrida con avisos nuevos, para no repetir avisos
entre una corrida y la siguiente. `data/avisos_del_dia.xlsx` no se versiona
(está en `.gitignore`): es un export descartable que se manda por Telegram
en cada corrida.

## Arquitectura

Ver `job_radar/` para el paquete Python. Cada fuente de avisos implementa
la interfaz `Scraper` de `job_radar/sources/base.py` (un `fetch()` que
devuelve `list[JobListing]`), para poder sumar sitios nuevos sin tocar el
resto del código.

## Sitio web

Alternativa al bot de Telegram: cada usuario se loguea, carga sus propios
perfiles de CV (nombre + keywords con pesos, lo mismo que `config.yaml`
pero editable desde la web y sin tocar código) y aprieta un botón para
generar el Excel al momento, sin esperar la corrida de las 9/18 hs.

**Arquitectura:**

- **Supabase** (Postgres + Auth): login por email/password y la tabla
  `cv_profiles` (`supabase/migrations/`). Row Level Security: cada usuario
  solo ve/edita sus propios perfiles (`auth.uid() = user_id`). El frontend
  habla directo con Supabase para todo el CRUD de perfiles.
- **Backend** (`api/`, FastAPI, deployado en Railway): un solo endpoint,
  `POST /generate`. Recibe el access token de Supabase del usuario
  logueado, lo reenvía tal cual a la REST API de Supabase para traer sus
  perfiles (RLS filtra, el backend no usa una service key ni tiene lógica
  de autorización propia), corre los scrapers y el scoring reusando
  `job_radar/` sin cambios, y devuelve el `.xlsx` armado en la respuesta.
  Sin dedup: cada click es una foto completa del momento, no "qué hay
  nuevo desde la última vez" como el bot de cron.
- **Frontend** (`web/`, Next.js, deployado en Vercel): login/signup,
  lista + alta/edición/borrado de perfiles, botón "Generar Excel" que
  llama al backend y dispara la descarga del archivo que devuelve.

**Variables de entorno:**

`api/` (Railway):
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`: del proyecto Supabase.
- `FRONTEND_ORIGINS`: dominios del frontend separados por coma, para CORS.

`web/` (Vercel, ver `web/.env.local.example` para desarrollo local):
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`: del mismo
  proyecto Supabase.
- `NEXT_PUBLIC_BACKEND_URL`: URL pública del backend en Railway.

**Desarrollo local del sitio:**

```bash
cd web
npm install
cp .env.local.example .env.local   # completar con tus valores
npm run dev
```

```bash
cd api
pip install -r ../requirements.txt
SUPABASE_URL=... SUPABASE_ANON_KEY=... uvicorn api.main:app --reload
```
