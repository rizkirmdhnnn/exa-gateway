// Exa Gateway dashboard v3. Standalone Hermes SDK bundle; no build step required.
(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;
  const { React } = SDK;
  const { useEffect, useState } = React;
  const API = "/api/plugins/exa-gateway";
  const card = { border: "1px solid var(--color-border)", borderRadius: 10, padding: 14, background: "var(--color-card)" };
  const button = { border: "1px solid var(--color-border)", borderRadius: 6, padding: "6px 10px", cursor: "pointer", background: "var(--color-card)" };
  const input = { border: "1px solid var(--color-border)", borderRadius: 6, padding: "7px 9px", minWidth: 150 };
  const get = (path) => fetch(API + path).then((r) => r.json());
  const post = (path, body) => fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined }).then((r) => r.json());
  const fmt = (value) => Number(value || 0).toLocaleString();
  const statusColor = (status) => status === "healthy" || status === "success" ? "#16a34a" : status === "rate_limited" ? "#d97706" : status === "error" || status === "upstream_error" ? "#dc2626" : "var(--color-muted-foreground)";
  function ActivityChart({ data }) {
    const values = data || [];
    const max = Math.max(1, ...values.map((v) => Number(v.requests || 0)));
    return React.createElement("div", { style: { ...card, minHeight: 170 } },
      React.createElement("h2", null, "Activity (hourly)"),
      values.length === 0 ? React.createElement("p", null, "No events in this period.") :
        React.createElement("div", { style: { display: "flex", alignItems: "end", gap: 5, height: 105, overflowX: "auto", paddingTop: 8 } }, values.map((v) =>
          React.createElement("div", { key: v.hour, title: `${v.requests} requests · ${v.errors} errors`, style: { height: `${Math.max(4, (Number(v.requests || 0) / max) * 100)}px`, width: 18, minWidth: 18, backgroundColor: v.errors ? "#dc2626" : "#2563eb", borderRadius: "4px 4px 0 0" } })
        )),
      values.length > 0 && React.createElement("small", null, "Blue: requests · Red: at least one error")
    );
  }
  function ExaGatewayPage() {
    const [summary, setSummary] = useState(null), [accounts, setAccounts] = useState({}), [events, setEvents] = useState([]), [activity, setActivity] = useState([]), [settings, setSettings] = useState(null);
    const [key, setKey] = useState(""), [message, setMessage] = useState(""), [tab, setTab] = useState("Overview"), [filter, setFilter] = useState(""), [healthFilter, setHealthFilter] = useState("all"), [page, setPage] = useState(0), [loading, setLoading] = useState(false), [showAdd, setShowAdd] = useState(false), [testProgress, setTestProgress] = useState(null);
    async function refresh() {
      setLoading(true);
      try { const [s, a, e, h, st] = await Promise.all([get("/summary"), get("/accounts"), get("/events?limit=50"), get("/activity?days=1"), get("/settings")]); setSummary(s); setAccounts(a.accounts || {}); setEvents(e.events || []); setActivity(h.activity || []); setSettings(st); } catch (e) { setMessage("Dashboard request failed"); } finally { setLoading(false); }
    }
    useEffect(() => { refresh(); }, []);
    async function mutate(path, options) { const data = await (options ? fetch(API + path, options).then((r) => r.json()) : post(path)); setMessage(data.detail || (data.ok ? "Saved" : "Request failed")); refresh(); }
    async function testKey(id) { const data = await post(`/test-key/${id}`); setMessage(`${data.status || "test failed"}${data.latency_ms ? ` · ${data.latency_ms} ms` : ""}`); refresh(); }
    async function testAll() {
      const ids = Object.values(accounts).filter((a) => a.enabled).map((a) => a.id);
      setTestProgress({ done: 0, total: ids.length });
      const results = await Promise.all(ids.map(async (id) => {
        try { return await post(`/test-key/${id}`); }
        catch (_) { return { ok: false }; }
      }));
      const ok = results.filter((result) => result.ok).length;
      setMessage(`Test complete: ${ok} healthy, ${results.length - ok} failed`);
      setTestProgress({ done: ids.length, total: ids.length });
      setTestProgress(null);
      refresh();
    }
    function addKey() { if (!key.trim()) return; mutate("/keys", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: key.trim() }) }); setKey(""); setShowAdd(false); }
    const allRows = Object.entries(accounts).filter(([id, a]) => (!filter || id.includes(filter) || (a.masked_key || "").includes(filter)) && (healthFilter === "all" || (healthFilter === "disabled" ? !a.enabled : healthFilter === (a.last_status || "unknown"))));
    const rows = allRows.slice(page * 10, page * 10 + 10);
    const stat = (label, value) => React.createElement("div", { style: card }, React.createElement("div", { style: { color: "var(--color-muted-foreground)", fontSize: 12 } }, label), React.createElement("strong", { style: { fontSize: 26 } }, String(value ?? 0)));
    return React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: 14, fontFamily: "system-ui" } },
      React.createElement("header", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 } }, React.createElement("div", null, React.createElement("h1", null, "Exa Gateway"), React.createElement("p", null, "Local key lifecycle, health, usage, events, and retention.")), React.createElement("button", { style: button, onClick: refresh }, loading ? "Refreshing..." : "Refresh")),
      React.createElement("nav", { style: { display: "flex", gap: 6, flexWrap: "wrap" } }, ["Overview", "Accounts", "Events", "Settings"].map((name) => React.createElement("button", { key: name, style: { ...button, fontWeight: tab === name ? 700 : 400 }, onClick: () => setTab(name) }, name))),
      message && React.createElement("div", { style: card }, message),
      tab === "Overview" && React.createElement(React.Fragment, null,
        React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10 } }, stat("Accounts", summary && summary.total_accounts), stat("Healthy", summary && summary.healthy_accounts), stat("Disabled", summary && summary.disabled_accounts), stat("Requests", summary && summary.requests), stat("Errors", summary && summary.errors), stat("Success rate", `${summary && summary.success_rate || 0}%`)),
        React.createElement(ActivityChart, { data: activity })),
      tab === "Accounts" && React.createElement("div", { style: card },
        React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12, alignItems: "center" } }, React.createElement("button", { style: button, onClick: () => setShowAdd(true) }, "Add account"), React.createElement("button", { style: button, disabled: !!testProgress, onClick: testAll }, testProgress ? `Testing ${testProgress.done}/${testProgress.total}...` : "Test all accounts"), React.createElement("input", { style: input, placeholder: "Search account", value: filter, onChange: (e) => { setFilter(e.target.value); setPage(0); } }), React.createElement("select", { style: input, value: healthFilter, onChange: (e) => { setHealthFilter(e.target.value); setPage(0); } }, ["all", "healthy", "unknown", "rate_limited", "upstream_error", "disabled"].map((x) => React.createElement("option", { key: x, value: x }, x))))
      , showAdd && React.createElement("div", { role: "dialog", style: { position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 } }, React.createElement("div", { style: { ...card, width: "min(520px,90vw)", background: "var(--color-card)" } }, React.createElement("h2", null, "Add Exa account"), React.createElement("p", null, "Paste the Exa API key. It will be stored locally in the protected SQLite database."), React.createElement("input", { style: { ...input, width: "100%", boxSizing: "border-box" }, placeholder: "Exa UUID API key", value: key, onChange: (e) => setKey(e.target.value), type: "password", autoFocus: true }), React.createElement("div", { style: { marginTop: 12, display: "flex", justifyContent: "flex-end", gap: 8 } }, React.createElement("button", { style: button, onClick: () => { setKey(""); setShowAdd(false); } }, "Cancel"), React.createElement("button", { style: button, onClick: addKey }, "Add account")))),
        rows.map(([id, a]) => React.createElement("div", { key: id, style: { borderTop: "1px solid var(--color-border)", padding: 10, display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" } }, React.createElement("div", null, React.createElement("strong", null, `Account ${id.split(":")[1]} · ${a.masked_key}`), React.createElement("div", null, `${fmt(a.requests)} requests · ${fmt(a.errors)} errors · ${a.last_latency_ms || 0} ms · `, React.createElement("span", { style: { color: statusColor(a.last_status) } }, a.enabled ? (a.last_status || "unknown") : "disabled"))), React.createElement("div", { style: { display: "flex", gap: 5 } }, React.createElement("button", { style: button, onClick: () => testKey(id.split(":")[1]) }, "Test"), React.createElement("button", { style: button, onClick: () => mutate(`/keys/${id.split(":")[1]}/${a.enabled ? "disable" : "enable"}`, { method: "POST" }) }, a.enabled ? "Disable" : "Enable"), React.createElement("button", { style: button, onClick: () => { if (confirm("Remove this key?")) mutate(`/keys/${id}`, { method: "DELETE" }); } }, "Remove")))),
        React.createElement("div", { style: { display: "flex", gap: 6, marginTop: 10 } }, React.createElement("button", { style: button, disabled: page === 0, onClick: () => setPage(page - 1) }, "Previous"), React.createElement("span", null, `Page ${page + 1}`), React.createElement("button", { style: button, disabled: rows.length < 10, onClick: () => setPage(page + 1) }, "Next"))),
      tab === "Events" && React.createElement("div", { style: card }, React.createElement("div", { style: { display: "flex", justifyContent: "space-between" } }, React.createElement("h2", null, "Recent events"), React.createElement("button", { style: button, onClick: () => mutate("/events/prune", { method: "POST" }) }, "Prune")), events.length === 0 ? React.createElement("p", null, "No events yet.") : events.map((e) => React.createElement("div", { key: e.id, style: { borderTop: "1px solid var(--color-border)", padding: 8 } }, new Date(e.created_at * 1000).toLocaleString(), " · ", e.operation, " · ", React.createElement("span", { style: { color: statusColor(e.status) } }, e.status), ` · ${e.latency_ms} ms · account ${e.key_id || "-"}`))),
      tab === "Settings" && React.createElement("div", { style: card }, React.createElement("h2", null, "Settings"), React.createElement("p", null, "Retention and event limits apply only to local event records."), React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" } }, React.createElement("label", null, "Retention days ", React.createElement("input", { style: input, type: "number", min: 1, max: 365, defaultValue: settings && settings.retention_days || 30, id: "exa-retention-days" })), React.createElement("label", null, "Maximum events ", React.createElement("input", { style: input, type: "number", min: 100, max: 100000, defaultValue: settings && settings.max_events || 10000, id: "exa-max-events" })), React.createElement("button", { style: button, onClick: () => mutate("/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ retention_days: Number(document.getElementById("exa-retention-days").value), max_events: Number(document.getElementById("exa-max-events").value) }) }) }, "Save settings")), React.createElement("div", { style: { marginTop: 12 } }, React.createElement("button", { style: button, onClick: () => { if (confirm("Prune old events now?")) mutate("/events/prune", { method: "POST" }); } }, "Prune events now"), ))
    );
  }
  window.__HERMES_PLUGINS__.register("exa-gateway", ExaGatewayPage);
})();