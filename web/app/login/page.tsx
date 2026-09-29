"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) router.replace("/dashboard");
    });
  }, [router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setLoading(true);

    if (mode === "login") {
      const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
      if (signInError) {
        setError(signInError.message);
      } else {
        router.replace("/dashboard");
      }
    } else {
      const { error: signUpError } = await supabase.auth.signUp({ email, password });
      if (signUpError) {
        setError(signUpError.message);
      } else {
        setInfo("Listo. Si tu proyecto pide confirmar el email, revisa tu casilla antes de entrar.");
      }
    }
    setLoading(false);
  }

  return (
    <>
      <h1>Job Radar</h1>
      <p className="subtitle">
        {mode === "login" ? "Inicia sesion para generar tu Excel de avisos." : "Crea una cuenta para empezar."}
      </p>

      <div className="card">
        <form onSubmit={handleSubmit}>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <label htmlFor="password">Contraseña</label>
          <input
            id="password"
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && <p className="error">{error}</p>}
          {info && <p className="muted">{info}</p>}

          <button type="submit" disabled={loading}>
            {loading ? "Un momento..." : mode === "login" ? "Iniciar sesion" : "Crear cuenta"}
          </button>
        </form>
      </div>

      <p className="muted">
        {mode === "login" ? "¿No tenes cuenta? " : "¿Ya tenes cuenta? "}
        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setError(null);
            setInfo(null);
          }}
        >
          {mode === "login" ? "Crear una" : "Iniciar sesion"}
        </button>
      </p>
    </>
  );
}
