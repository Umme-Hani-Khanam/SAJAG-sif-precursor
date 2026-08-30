import React from "react";
import { login } from "../api/phase3.js";
import { html } from "../ui.js";

export function LoginPage({ onAuthenticated, backendOnline }) {
  const [identifier, setIdentifier] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await login(identifier, password);
      window.localStorage.setItem("sajagAccessToken", result.access_token);
      window.localStorage.setItem("sajagUser", JSON.stringify(result.user));
      onAuthenticated(result.user);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return html`<main className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-12"><div className="w-full max-w-md rounded-[2rem] bg-white p-8 shadow-2xl"><div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500 text-xl font-black text-slate-950">S</div><p className="eyebrow mt-6">SAJAG SECURE ACCESS</p><h1 className="mt-2 text-3xl font-bold">Sign in</h1><p className="mt-2 text-sm leading-6 text-slate-500">Use your assigned account. Access to reports, actions, and evidence is limited by role and site scope.</p><form className="mt-7 space-y-4" onSubmit=${submit}><label><span className="filter-label">Username or email</span><input className="filter-control" autoComplete="username" value=${identifier} onChange=${(e) => setIdentifier(e.target.value)} required /></label><label><span className="filter-label">Password</span><input className="filter-control" type="password" autoComplete="current-password" value=${password} onChange=${(e) => setPassword(e.target.value)} required /></label>${error ? html`<div className="error-box" role="alert">${error}</div>` : null}<button className="primary-button w-full" disabled=${busy || !backendOnline}>${busy ? "Signing in…" : backendOnline ? "Sign in" : "Backend offline"}</button></form><p className="mt-6 text-xs text-slate-400">Sessions expire automatically. Passwords and session tokens are never displayed.</p></div></main>`;
}
