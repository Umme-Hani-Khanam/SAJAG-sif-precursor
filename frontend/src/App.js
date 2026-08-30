import React from "react";
import { checkBackendHealth } from "./api/reports.js";
import { html } from "./ui.js";
import { AnalyzePage } from "./components/AnalyzePage.js";
import { AppHeader } from "./components/AppHeader.js";
import { DashboardPage } from "./components/DashboardPage.js";
import { EmergingRisksPage } from "./components/EmergingRisksPage.js";
import { PatternsPage } from "./components/PatternsPage.js";
import { ReportsPage } from "./components/ReportsPage.js";
import { ActionsPage } from "./components/ActionsPage.js";
import { AuditPage } from "./components/AuditPage.js";
import { KnowledgePage } from "./components/KnowledgePage.js";
import { LoginPage } from "./components/LoginPage.js";
import { ValidationPage } from "./components/ValidationPage.js";
import { me, logout } from "./api/phase3.js";

const PAGES = { dashboard: DashboardPage, analyze: AnalyzePage, emerging: EmergingRisksPage, patterns: PatternsPage, reports: ReportsPage, actions: ActionsPage, audit: AuditPage, knowledge: KnowledgePage, validation: ValidationPage };

export function App() {
  const initial = window.location.hash.replace("#", "");
  const [page, setPage] = React.useState(PAGES[initial] ? initial : "dashboard");
  const [online, setOnline] = React.useState(false);
  const [demoMode, setDemoMode] = React.useState(null);
  const storedUser = (() => { try { return JSON.parse(window.localStorage.getItem("sajagUser")); } catch { return null; } })();
  const [user, setUser] = React.useState(storedUser);
  const [actor, setActor] = React.useState({
    name: window.localStorage.getItem("sajagActorName") || "Demo HSE Manager",
    role: window.localStorage.getItem("sajagActorRole") || "HSE_MANAGER",
  });
  React.useEffect(() => {
    checkBackendHealth().then((health) => {
      const isDemo = Boolean(health.demo_mode);
      window.localStorage.setItem("sajagDemoMode", String(isDemo));
      setOnline(true);
      setDemoMode(isDemo);
      if (!isDemo && window.localStorage.getItem("sajagAccessToken")) me().then(setUser).catch(() => { window.localStorage.removeItem("sajagAccessToken"); window.localStorage.removeItem("sajagUser"); setUser(null); });
    }).catch(() => { window.localStorage.setItem("sajagDemoMode", "false"); setOnline(false); setDemoMode(false); });
    const handleHash = () => { const next = window.location.hash.replace("#", ""); if (PAGES[next]) setPage(next); };
    window.addEventListener("hashchange", handleHash); return () => window.removeEventListener("hashchange", handleHash);
  }, []);
  function navigate(next) { window.location.hash = next; setPage(next); window.scrollTo({ top: 0, behavior: "smooth" }); }
  function changeActor(next) {
    const named = {
      ...next,
      name: next.role !== actor.role ? `Demo ${next.role.replaceAll("_", " ")}` : (next.name || `Demo ${next.role.replaceAll("_", " ")}`),
    };
    window.localStorage.setItem("sajagActorName", named.name);
    window.localStorage.setItem("sajagActorRole", named.role);
    setActor(named);
  }
  const Page = PAGES[page];
  if (demoMode === null) return html`<div className="flex min-h-screen items-center justify-center">Connecting to SAJAG…</div>`;
  if (!demoMode && !user) return html`<${LoginPage} backendOnline=${online} onAuthenticated=${(next) => { setUser(next); setActor({ name: next.name, role: next.role, site_scope: next.site_scope }); }} />`;
  const activeActor = demoMode ? actor : { name: user.name, role: user.role, site_scope: user.site_scope };
  async function signOut() { try { await logout(); } catch {} window.localStorage.removeItem("sajagAccessToken"); window.localStorage.removeItem("sajagUser"); setUser(null); }
  return html`<div className="min-h-screen bg-slate-50 text-slate-900"><${AppHeader} currentPage=${page} onNavigate=${navigate} backendOnline=${online} actor=${activeActor} onActorChange=${changeActor} demoMode=${demoMode} onLogout=${signOut} /><main className="mx-auto w-full max-w-[1500px] px-4 py-7 lg:px-8"><${Page} actor=${activeActor} /></main><footer className="mx-auto max-w-[1500px] px-8 pb-8 text-xs text-slate-400">SAJAG supports HSE decision-making. It does not predict fatalities with certainty.</footer></div>`;
}
