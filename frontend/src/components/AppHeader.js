import React from "react";
import { getNotifications, getUnreadCount, markAllNotificationsRead, markNotificationRead } from "../api/phase3.js";
import { html } from "../ui.js";

const NAV_ITEMS = [
  ["dashboard", "Dashboard"],
  ["analyze", "Analyze"],
  ["emerging", "Emerging Risks"],
  ["patterns", "Patterns"],
  ["reports", "Reports"],
  ["actions", "Actions"],
  ["audit", "Audit"],
  ["knowledge", "Knowledge"],
  ["validation", "Validation"],
];

export function AppHeader({ currentPage, onNavigate, backendOnline, actor, onActorChange, demoMode, onLogout }) {
  const [open, setOpen] = React.useState(false); const [notifications, setNotifications] = React.useState([]); const [unread, setUnread] = React.useState(0);
  const [notificationView, setNotificationView] = React.useState("unread");
  const load = React.useCallback(() => { if (!backendOnline) return; Promise.all([getUnreadCount(), getNotifications()]).then(([count, items]) => { setUnread(count.unread); setNotifications(items); }).catch(() => {}); }, [backendOnline, actor.role]);
  React.useEffect(() => { load(); const timer = window.setInterval(load, 30000); return () => window.clearInterval(timer); }, [load]);
  const navItems = NAV_ITEMS.filter(([key]) => key !== "validation" || ["HSE_MANAGER", "ADMIN"].includes(actor.role));
  async function markOne(id) { await markNotificationRead(id); await load(); }
  async function markAll() { await markAllNotificationsRead(); await load(); }
  async function openNotification(item) { await markOne(item.notification_id); setOpen(false); const target = { REPORT: "reports", CAPA: "actions", DOCUMENT: "knowledge", ALERT: "emerging" }[item.entity_type]; if (target) onNavigate(target); }
  const shownNotifications = notificationView === "unread" ? notifications.filter((item) => !item.read_at) : notifications;
  return html`
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 shadow-sm backdrop-blur">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <button type="button" onClick=${() => onNavigate("dashboard")} className="flex items-center gap-3 text-left">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-lg font-bold text-white">S</span>
          <span>
            <span className="block text-sm font-extrabold tracking-[0.2em] text-slate-900">SAJAG</span>
            <span className="block text-xs text-slate-500">SIF Precursor Intelligence</span>
          </span>
        </button>

        <nav className="flex gap-1 overflow-x-auto" aria-label="Application navigation">
          ${navItems.map(([key, label]) => html`
            <button
              key=${key}
              type="button"
              onClick=${() => onNavigate(key)}
              className=${`whitespace-nowrap rounded-xl px-3.5 py-2 text-sm font-semibold transition ${
                currentPage === key ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >${label}</button>
          `)}
        </nav>

        <div className="flex items-center gap-2">
          ${demoMode ? html`<div><label className="sr-only" htmlFor="role-selector">Demo role</label>
          <select id="role-selector" className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-2 text-xs font-semibold text-slate-700" value=${actor.role} onChange=${(event) => onActorChange({ ...actor, role: event.target.value })}>
            ${["WORKER", "SITE_SUPERVISOR", "HSE_OFFICER", "HSE_MANAGER", "AUDITOR", "ADMIN"].map((role) => html`<option key=${role} value=${role}>${role.replaceAll("_", " ")}</option>`)}
          </select></div>` : html`<div className="hidden text-right xl:block"><p className="text-xs font-bold">${actor.name}</p><p className="text-[10px] text-slate-500">${actor.role.replaceAll("_", " ")} · ${(actor.site_scope || []).join(", ") || "No sites"}</p></div>`}
          <div className="relative"><button className="relative rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" aria-label="Notifications" onClick=${() => setOpen(!open)}>🔔${unread ? html`<span className="absolute -right-2 -top-2 min-w-5 rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white">${unread}</span>` : null}</button>${open ? html`<div className="absolute right-0 mt-2 w-[min(24rem,90vw)] rounded-2xl border border-slate-200 bg-white p-3 shadow-xl"><div className="flex items-center justify-between"><b className="text-sm">Notifications</b><button className="text-xs font-semibold text-cyan-700" onClick=${markAll}>Mark all read</button></div><div className="mt-3 flex gap-2"><button className=${`rounded-lg px-3 py-1 text-xs font-bold ${notificationView === "unread" ? "bg-slate-900 text-white" : "bg-slate-100"}`} onClick=${() => setNotificationView("unread")}>Unread (${unread})</button><button className=${`rounded-lg px-3 py-1 text-xs font-bold ${notificationView === "all" ? "bg-slate-900 text-white" : "bg-slate-100"}`} onClick=${() => setNotificationView("all")}>All</button></div><div className="mt-2 max-h-80 space-y-2 overflow-auto">${shownNotifications.length ? shownNotifications.slice(0, 20).map((item) => html`<button key=${item.notification_id} className=${`w-full rounded-xl p-3 text-left ${item.read_at ? "bg-white" : "bg-cyan-50"}`} onClick=${() => openNotification(item)}><p className="text-xs font-bold">${item.title}</p><p className="mt-1 text-xs text-slate-500">${item.message}</p></button>`) : html`<p className="p-5 text-center text-xs text-slate-500">No ${notificationView} notifications.</p>`}</div></div>` : null}</div>
          ${!demoMode ? html`<button className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold" onClick=${onLogout}>Sign out</button>` : null}
          <div className=${`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${
            backendOnline ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-700"
          }`}>
            <span className=${`h-2 w-2 rounded-full ${backendOnline ? "bg-emerald-500" : "bg-rose-500"}`}></span>
            ${backendOnline ? "Online" : "Offline"}
          </div>
        </div>
      </div>
    </header>
  `;
}
