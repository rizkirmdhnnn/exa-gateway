// ~/.hermes/plugins/web/exa-gateway/dashboard/dist/index.js
// Exa Gateway dashboard — manage keys, watch per-account stats.
// NOTE: dashboard plugins don't get Tailwind classes — use inline styles.
(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;
  const { React, components } = SDK;
  const { Card, CardHeader, CardTitle, CardContent, Button, Input } = components;
  const { useState, useEffect } = React;
  const API = "/api/plugins/exa-gateway";

  const CARD = { border: "1px solid var(--color-border)", borderRadius: "12px", padding: "16px", background: "var(--color-card)" };
  const HEAD = { fontSize: "13px", fontWeight: 600, color: "var(--color-muted-foreground)", textTransform: "uppercase", letterSpacing: "0.05em" };

  function fmt(n) { return n.toLocaleString(); }

  function ExaGatewayPage() {
    const [health, setHealth] = useState(null);
    const [accounts, setAccounts] = useState(null);
    const [newKey, setNewKey] = useState("");
    const [msg, setMsg] = useState("");
    const [loading, setLoading] = useState(true);

    async function refresh() {
      try {
        const h = await fetch(`${API}/health`).then((r) => r.json());
        const a = await fetch(`${API}/accounts`).then((r) => r.json());
        setHealth(h);
        setAccounts(a.accounts || {});
      } catch (e) {
        setMsg("Failed to load: " + e);
      } finally {
        setLoading(false);
      }
    }

    useEffect(() => { refresh(); }, []);

    async function addKey() {
      const key = newKey.trim();
      if (!key) return;
      try {
        const r = await fetch(`${API}/keys`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key }),
        });
        const d = await r.json();
        setMsg(d.ok ? "Key added!" : "Error: " + (d.detail || "unknown"));
        setNewKey("");
        refresh();
      } catch (e) {
        setMsg("Error: " + e);
      }
    }

    async function removeKey(accountId) {
      try {
        await fetch(`${API}/keys/${accountId}`, { method: "DELETE" });
        refresh();
      } catch (e) {
        setMsg("Error: " + e);
      }
    }

    const accountList = Object.entries(accounts || {});

    return React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: "16px" } },
      // Header
      React.createElement("div", null,
        React.createElement("h1", { style: { fontSize: "20px", fontWeight: 700 } }, "Exa Gateway"),
        React.createElement("p", { style: { color: "var(--color-muted-foreground)", fontSize: "13px" } },
          "Multi-account Exa search/extract with round-robin failover — no container needed."
        ),
      ),

      // Add key
      React.createElement("div", { style: { ...CARD, display: "flex", gap: "8px", alignItems: "center" } },
        React.createElement(Input, {
          placeholder: "Paste Exa API key...",
          value: newKey,
          onChange: (e) => setNewKey(e.target.value),
          style: { flex: 1 },
        }),
        React.createElement(Button, { onClick: addKey }, "Add key"),
      ),

      // Status message
      msg ? React.createElement("p", { style: { color: "var(--color-muted-foreground)", fontSize: "13px" } }, msg) : null,

      // Stats cards
      React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "12px" } },
        React.createElement("div", { style: CARD },
          React.createElement("div", { style: HEAD }, "Accounts"),
          React.createElement("div", { style: { fontSize: "28px", fontWeight: 700 } }, fmt(health ? health.accounts : 0)),
        ),
        React.createElement("div", { style: CARD },
          React.createElement("div", { style: HEAD }, "Total requests"),
          React.createElement("div", { style: { fontSize: "28px", fontWeight: 700 } },
            fmt(Object.values(accountList).reduce((s, [, v]) => s + (v.requests || 0), 0))),
        ),
        React.createElement("div", { style: CARD },
          React.createElement("div", { style: HEAD }, "Total errors"),
          React.createElement("div", { style: { fontSize: "28px", fontWeight: 700 } },
            fmt(Object.values(accountList).reduce((s, [, v]) => s + (v.errors || 0), 0))),
        ),
        React.createElement("div", { style: CARD },
          React.createElement("div", { style: HEAD }, "Status"),
          React.createElement("div", { style: { fontSize: "20px", fontWeight: 600, color: health && health.accounts > 0 ? "#22c55e" : "#ef4444" } },
            health && health.accounts > 0 ? "● Active" : "● No keys"),
        ),
      ),

      // Accounts table
      React.createElement("div", { style: CARD },
        React.createElement(CardHeader, null,
          React.createElement(CardTitle, null, "Accounts"),
        ),
        React.createElement(CardContent, null,
          accountList.length === 0
            ? React.createElement("p", { style: { color: "var(--color-muted-foreground)" } }, "No accounts yet — add your first Exa API key above.")
            : accountList.map(([accountId, v]) =>
                React.createElement("div", {
                  key: accountId,
                  style: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--color-border)" },
                },
                  React.createElement("div", null,
                    React.createElement("div", { style: { fontWeight: 600, fontSize: "13px" } }, accountId.split(":")[1]),
                    React.createElement("div", { style: { color: "var(--color-muted-foreground)", fontSize: "12px" } },
                      `${fmt(v.requests || 0)} req · ${v.errors || 0} errors` + (v.last_error ? ` · ${v.last_error}` : "")),
                  ),
                  React.createElement(Button, { onClick: () => removeKey(accountId), variant: "destructive", size: "sm" }, "Remove"),
                )
              ),
        ),
      ),
    );
  }

  window.__HERMES_PLUGINS__.register("exa-gateway", ExaGatewayPage);
})();
