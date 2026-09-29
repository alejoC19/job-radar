create table public.job_listings (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  url text not null unique,
  title text not null,
  company text not null default '',
  location text not null default '',
  description text not null default '',
  salary_text text,
  scraped_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create index job_listings_scraped_at_idx on public.job_listings (scraped_at desc);

alter table public.job_listings enable row level security;

-- Solo usuarios logueados pueden leer (el sitio matchea contra esto). No es
-- informacion sensible, pero mantiene el mismo criterio que el resto de la app.
create policy "job_listings_select_authenticated" on public.job_listings
  for select to authenticated using (true);

-- No hay policy de insert/update/delete directa: el unico camino de escritura
-- es esta funcion SECURITY DEFINER, para no depender de una service key que
-- el backend no tiene. El cron scrapea con la anon key, asi que la funcion
-- queda ejecutable por el rol anon (ver README: es un tradeoff aceptado para
-- una herramienta personal, no hay datos sensibles en juego).
create or replace function public.ingest_job_listings(payload jsonb)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  affected_count integer;
begin
  with rows as (
    select
      (item->>'source')::text as source,
      (item->>'url')::text as url,
      (item->>'title')::text as title,
      coalesce(item->>'company', '') as company,
      coalesce(item->>'location', '') as location,
      coalesce(item->>'description', '') as description,
      item->>'salary_text' as salary_text
    from jsonb_array_elements(payload) as item
    where item->>'url' is not null and item->>'title' is not null
  ),
  upserted as (
    insert into public.job_listings (source, url, title, company, location, description, salary_text)
    select source, url, title, company, location, description, salary_text from rows
    on conflict (url) do update set
      title = excluded.title,
      company = excluded.company,
      location = excluded.location,
      description = excluded.description,
      salary_text = excluded.salary_text,
      last_seen_at = now()
    returning 1
  )
  select count(*) into affected_count from upserted;
  return affected_count;
end;
$$;

revoke all on function public.ingest_job_listings(jsonb) from public;
grant execute on function public.ingest_job_listings(jsonb) to anon, authenticated;

-- Mantiene la tabla chica: se llama una vez por corrida del cron. 30 dias de
-- margen (no 15) para no pisarle el pie al filtro de "ultimos 15 dias" del
-- matching por ningun huso horario/retraso de corrida.
create or replace function public.cleanup_old_job_listings()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  deleted_count integer;
begin
  delete from public.job_listings where scraped_at < now() - interval '30 days';
  get diagnostics deleted_count = row_count;
  return deleted_count;
end;
$$;

revoke all on function public.cleanup_old_job_listings() from public;
grant execute on function public.cleanup_old_job_listings() to anon, authenticated;
