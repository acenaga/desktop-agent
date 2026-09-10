import React from "react";
import { HealthStatus } from "../types";

interface NavbarProps {
  currentTab: "new" | "execution" | "history" | "settings";
  onSelectTab: (tab: "new" | "execution" | "history" | "settings") => void;
  health: HealthStatus | null;
  isInteracting: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onSelectTab,
  health,
  isInteracting,
}) => {
  return (
    <header style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-secondary)" }}>
      {/* Banner persistente de uso de mouse/teclado según Sección 12 */}
      {isInteracting && (
        <div style={{
          background: "var(--warning)",
          color: "#000",
          textAlign: "center",
          padding: "6px",
          fontWeight: "bold",
          fontSize: "13px",
        }}>
          ⚠️ El agente está interactuando con el teclado o ratón. No toques la ventana autorizada para no perder el foco.
        </div>
      )}

      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 24px",
        maxWidth: 1200,
        margin: "0 auto",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "20px", fontWeight: "bold", color: "var(--accent-primary)" }}>
            ⚡ LocalDesk
          </span>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)", background: "var(--bg-card)", padding: "2px 6px", borderRadius: "4px" }}>
            v0.1.0 (Local Only)
          </span>
        </div>

        <nav style={{ display: "flex", gap: "8px" }}>
          <button
            className={currentTab === "new" ? "btn-primary" : "btn-secondary"}
            onClick={() => onSelectTab("new")}
          >
            Nueva Tarea
          </button>
          <button
            className={currentTab === "execution" ? "btn-primary" : "btn-secondary"}
            onClick={() => onSelectTab("execution")}
          >
            Ejecución
          </button>
          <button
            className={currentTab === "history" ? "btn-primary" : "btn-secondary"}
            onClick={() => onSelectTab("history")}
          >
            Historial
          </button>
          <button
            className={currentTab === "settings" ? "btn-primary" : "btn-secondary"}
            onClick={() => onSelectTab("settings")}
          >
            Configuración
          </button>
        </nav>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px" }}>
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor: health?.inference_available ? "var(--success)" : "var(--danger)",
            }}
          />
          <span style={{ color: "var(--text-secondary)" }}>
            {health?.inference_available ? (health.model_id || "Ollama Conectado") : "Inferencia No Lista"}
          </span>
        </div>
      </div>
    </header>
  );
};
