"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabaseClient";
import { CvProfile, parseKeywordsText, keywordsToText } from "@/lib/profiles";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL!;

export default function DashboardPage() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [profiles, setProfiles] = useState<CvProfile[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState(true);
  const [editing, setEditing] = useState<CvProfile | "new" | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace("/login");
        return;
      }
      setSession(data.session);
    });
  }, [router]);

  useEffect(() => {
    if (session) loadProfiles();
  }, [session]);

  async function loadProfiles() {
    setLoadingProfiles(true);
    const { data, error } = await supabase
      .from("cv_profiles")
      .select("id,name,keywords,created_at")
      .order("created_at", { ascending: true });
    if (!error && data) setProfiles(data as CvProfile[]);
    setLoadingProfiles(false);
  }

  async function handleDelete(id: string) {
    if (!confirm("¿Borrar este perfil?")) return;
    await supabase.from("cv_profiles").delete().eq("id", id);
    loadProfiles();
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  async function handleGenerate() {
    setGenerating(true);
    setGenerateError(null);
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) throw new Error("Sesion vencida, volve a iniciar sesion.");

      const response = await fetch(`${BACKEND_URL}/generate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || `Error ${response.status} generando el Excel`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "avisos_job_radar.xlsx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Error generando el Excel");
    } finally {
      setGenerating(false);
    }
  }

  if (!session) return <p className="muted">Cargando...</p>;

  return (
    <>
      <div className="top-bar">
        <h1>Job Radar</h1>
        <button type="button" className="secondary" onClick={handleSignOut}>
          Salir
        </button>
      </div>

      <div className="card">
        <div className="row-between">
          <div>
            <h2>Generar Excel</h2>
            <p className="muted">
              Corre los scrapers ahora mismo contra tus perfiles y te descarga el Excel con los avisos
              encontrados (puede tardar unos 20-30 segundos).
            </p>
          </div>
        </div>
        <button type="button" onClick={handleGenerate} disabled={generating || profiles.length === 0}>
          {generating ? "Generando..." : "Generar Excel"}
        </button>
        {profiles.length === 0 && !loadingProfiles && (
          <p className="muted" style={{ marginTop: 10 }}>
            Cargate al menos un perfil de CV para poder generar el Excel.
          </p>
        )}
        {generateError && <p className="error" style={{ marginTop: 10 }}>{generateError}</p>}
      </div>

      <div className="row-between" style={{ marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Tus perfiles de CV</h2>
        {editing === null && (
          <button type="button" onClick={() => setEditing("new")}>
            Nuevo perfil
          </button>
        )}
      </div>

      {editing !== null && (
        <ProfileForm
          userId={session.user.id}
          profile={editing === "new" ? null : editing}
          onDone={() => {
            setEditing(null);
            loadProfiles();
          }}
          onCancel={() => setEditing(null)}
        />
      )}

      {loadingProfiles ? (
        <p className="muted">Cargando perfiles...</p>
      ) : profiles.length === 0 ? (
        <p className="muted">Todavia no tenes perfiles cargados.</p>
      ) : (
        profiles.map((profile) => (
          <div className="card" key={profile.id}>
            <div className="row-between">
              <div>
                <strong>{profile.name}</strong>
                <p className="muted" style={{ margin: "4px 0 0" }}>
                  {Object.keys(profile.keywords).length} keywords
                </p>
              </div>
              <div className="row">
                <button type="button" className="secondary" onClick={() => setEditing(profile)}>
                  Editar
                </button>
                <button type="button" className="danger" onClick={() => handleDelete(profile.id)}>
                  Borrar
                </button>
              </div>
            </div>
          </div>
        ))
      )}
    </>
  );
}

function ProfileForm({
  userId,
  profile,
  onDone,
  onCancel,
}: {
  userId: string;
  profile: CvProfile | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(profile?.name ?? "");
  const [keywordsText, setKeywordsText] = useState(profile ? keywordsToText(profile.keywords) : "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const keywords = parseKeywordsText(keywordsText);
    const payload = { name, keywords, user_id: userId };

    const { error: saveError } = profile
      ? await supabase.from("cv_profiles").update(payload).eq("id", profile.id)
      : await supabase.from("cv_profiles").insert(payload);

    if (saveError) {
      setError(saveError.message);
      setSaving(false);
      return;
    }
    onDone();
  }

  return (
    <div className="card">
      <form onSubmit={handleSubmit}>
        <label htmlFor="name">Nombre del perfil</label>
        <input id="name" type="text" required value={name} onChange={(e) => setName(e.target.value)} />

        <label htmlFor="keywords">
          Keywords (una por linea, formato &quot;keyword: peso&quot;. Sin peso, se usa 1)
        </label>
        <textarea
          id="keywords"
          placeholder={"react: 3\nnode: 2\ntypescript: 3"}
          value={keywordsText}
          onChange={(e) => setKeywordsText(e.target.value)}
        />

        {error && <p className="error">{error}</p>}

        <div className="row">
          <button type="submit" disabled={saving}>
            {saving ? "Guardando..." : "Guardar"}
          </button>
          <button type="button" className="secondary" onClick={onCancel}>
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}
