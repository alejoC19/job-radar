create table public.cv_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name text not null,
  keywords jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index cv_profiles_user_id_idx on public.cv_profiles(user_id);

alter table public.cv_profiles enable row level security;

create policy "cv_profiles_select_own" on public.cv_profiles
  for select using (auth.uid() = user_id);

create policy "cv_profiles_insert_own" on public.cv_profiles
  for insert with check (auth.uid() = user_id);

create policy "cv_profiles_update_own" on public.cv_profiles
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "cv_profiles_delete_own" on public.cv_profiles
  for delete using (auth.uid() = user_id);

create function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger cv_profiles_set_updated_at
  before update on public.cv_profiles
  for each row execute function public.set_updated_at();
