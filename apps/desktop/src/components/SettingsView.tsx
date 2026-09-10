import React, { useState } from "react";
import { HealthStatus, ModelItem, TaskScope } from "../types";

interface SettingsViewProps {
  health: HealthStatus | null;
  models: ModelItem[];
  scopes: TaskScope[];
  onRefreshModels: () => void;
  onSavePreference: (key: string, value: any) => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  health,
  models,
  scopes,
  onRefreshModels,
  onSavePreference,
}) => {
  const [selectedModel, setSelectedModel] = useState(health?.model_id || "");
  const [retentionDays, setRetentionDays] = useState(30);

  return (
    <div style={{ maxWidth: 900, margin: "24px auto" }}>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Configuración y Diagnóstico</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
          Gestión del modelo local de inferencia, capacidades, permisos de carpetas y privacidad.
        </p>

        {/* Diagnóstico del Entorno */}
        <div style={{ marginBottom: "24px" }}>
          <h3>Diagnóstico del Sistema</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", background: "var(--bg-primary)", padding: "16px", borderRadius: "8px" }}>
            <div><strong>Sistema Operativo:</strong> {health?.os_platform || "Detectando..."}</div>
            <div><strong>Adaptador de Escritorio:</strong> {health?.desktop_adapter || "N/A"}</div>
            <div><strong>Inferencia Ollama:</strong> {health?.inference_available ? "✅ Disponible" : "❌ No disponible"}</div>
            <div><strong>Versión LocalDesk:</strong> {health?.version || "0.1.0"}</div>
          </div>
        </div>

        {/* Selección y Comprobación de Modelos */}
        <div style={{ marginBottom: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <h3 style={{ margin: 0 }}>Modelos Locales Instalados</h3>
            <button className="btn-secondary" onClick={onRefreshModels}>
              🔄 Actualizar Modelos
            </button>
          </div>

          {models.length === 0 ? (
            <div style={{ padding: "16px", background: "var(--bg-primary)", borderRadius: "8px" }}>
              <p style={{ margin: "0 0 8px 0", color: "var(--warning)" }}>
                No se detectaron modelos instalados en Ollama local.
              </p>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)" }}>
                Puedes descargar un modelo compatible en tu terminal ejecutando: <code>ollama pull qwen2.5:14b</code> o <code>ollama pull llama3.2:3b</code>.
                Mientras tanto, las pruebas y simulaciones deterministas con <code>FakeModelProvider</code> siguen operativas.
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {models.map((m) => (
                <div
                  key={m.name}
                  style={{
                    padding: "12px",
                    background: selectedModel === m.name ? "var(--bg-card)" : "var(--bg-primary)",
                    borderRadius: "6px",
                    border: `1px solid ${selectedModel === m.name ? "var(--accent-primary)" : "var(--border)"}`,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <strong>{m.name}</strong>
                    {m.is_simulation && <span style={{ marginLeft: "8px", fontSize: "11px", color: "var(--warning)" }}>(Simulación)</span>}
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px" }}>
                      Contexto: {m.context_length} tokens | Cuantización: {m.quantization || "N/D"} | Herramientas: {m.supports_tools ? "Sí" : "No"} | Visión: {m.supports_vision ? "Sí" : "No"}
                    </div>
                  </div>
                  <button
                    className={selectedModel === m.name ? "btn-primary" : "btn-secondary"}
                    onClick={() => {
                      setSelectedModel(m.name);
                      onSavePreference("model_id", m.name);
                    }}
                  >
                    {selectedModel === m.name ? "Seleccionado" : "Usar este"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Carpetas Autorizadas */}
        <div style={{ marginBottom: "24px" }}>
          <h3>Alcances y Carpetas Autorizadas</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {scopes.map((s) => (
              <div key={s.scope_id} style={{ padding: "12px", background: "var(--bg-primary)", borderRadius: "6px" }}>
                <strong>{s.name}</strong>
                <div style={{ fontSize: "13px", marginTop: "4px" }}>
                  <div>Lectura: {s.read_roots.join(", ") || "(Ninguna)"}</div>
                  <div>Escritura: {s.write_roots.join(", ") || "(Ninguna)"}</div>
                  <div>Apps: {s.allowed_apps.join(", ") || "Todas"}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Privacidad y Retención */}
        <div>
          <h3>Privacidad y Retención Local</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "14px" }}>
            <div>
              🔒 <strong>Inferencia 100% Local:</strong> Sin telemetría remota ni almacenamiento en la nube.
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <label>Retención de historial (días):</label>
              <input
                type="number"
                value={retentionDays}
                onChange={(e) => {
                  const v = parseInt(e.target.value) || 30;
                  setRetentionDays(v);
                  onSavePreference("history_retention_days", v);
                }}
                style={{ width: "80px" }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
