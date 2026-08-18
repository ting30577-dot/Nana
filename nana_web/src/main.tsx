import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { browserTransportDependencies, ProjectionStore } from "./store";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) throw new Error("Nana root element is missing");
const appRoot = root;

function isPackagedShellLocation(): boolean {
  const location = new URL(window.location.href);
  const packagedOrigin =
    (location.protocol === "tauri:" && location.hostname === "localhost") ||
    ((location.protocol === "http:" || location.protocol === "https:") &&
      location.hostname === "tauri.localhost");
  return packagedOrigin && location.port === "";
}

async function browserAuthorization(): Promise<string | null> {
  try {
    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const bootstrapSecret = fragment.get("bootstrap");
    history.replaceState(null, "", window.location.pathname + window.location.search);
    const response = await fetch(
      bootstrapSecret ? "/api/v1/session/exchange" : "/api/v1/session/restore",
      {
        method: "POST",
        credentials: "same-origin",
        headers: bootstrapSecret
          ? { "Content-Type": "application/json", "X-Nana-Bootstrap": "1" }
          : { "Content-Type": "application/json", "X-Nana-Session-Restore": "1" },
        body: JSON.stringify(bootstrapSecret ? { bootstrap_secret: bootstrapSecret } : {}),
      },
    );
    if (!response.ok) return null;
    const payload: unknown = await response.json();
    if (payload === null || typeof payload !== "object" || Array.isArray(payload)) return null;
    const authorization = (payload as Record<string, unknown>).authorization;
    return typeof authorization === "string" && authorization.startsWith("Bearer ")
      ? authorization
      : null;
  } catch {
    return null;
  }
}

function renderApp(authorization: string | null): void {
  const transport = browserTransportDependencies();
  const store = new ProjectionStore({ ...transport, authorization: () => authorization });
  createRoot(appRoot).render(<StrictMode><App store={store} /></StrictMode>);
}

if (isPackagedShellLocation()) {
  renderApp(null);
} else {
  void browserAuthorization().then(renderApp);
}
