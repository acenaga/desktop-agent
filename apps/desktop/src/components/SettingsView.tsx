import React, { useEffect, useState } from "react";
import { HealthStatus, ModelItem, TaskScope } from "../types";

interface SettingsViewProps {
  health: HealthStatus | null;
  models: ModelItem[];
  scopes: TaskScope[];
  onRefreshModels: () => void;
  onSavePreference: (key: string, value: any) => void;
  onUpdateScopeRoots: (
    scopeId: string,
    data: { read_roots: string[]; write_roots: string[] }
  ) => Promise<TaskScope>;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  health,
  models,
  scopes,
  onRefreshModels,
  onSavePreference,
  onUpdateScopeRoots,
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
              <ScopeRootsEditor key={s.scope_id} scope={s} onSave={onUpdateScopeRoots} />
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

// Una ruta por línea, igual que las referencias de entrada en TaskNewView
const parseRoots = (text: string): string[] =>
  text
    .split("\n")
    .map((r) => r.trim())
    .filter((r) => r.length > 0);

interface ScopeRootsEditorProps {
  scope: TaskScope;
  onSave: SettingsViewProps["onUpdateScopeRoots"];
}

const ScopeRootsEditor: React.FC<ScopeRootsEditorProps> = ({ scope, onSave }) => {
  const [readText, setReadText] = useState(scope.read_roots.join("\n"));
  const [writeText, setWriteText] = useState(scope.write_roots.join("\n"));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedVersion, setSavedVersion] = useState<number | null>(null);

  // Al guardar, el backend devuelve rutas canónicas y una versión nueva: reflejarlas
  useEffect(() => {
    setReadText(scope.read_roots.join("\n"));
    setWriteText(scope.write_roots.join("\n"));
  }, [scope.scope_id, scope.version]);

  const readRoots = parseRoots(readText);
  const writeRoots = parseRoots(writeText);
  const isDirty =
    readRoots.join("\n") !== scope.read_roots.join("\n") ||
    writeRoots.join("\n") !== scope.write_roots.join("\n");

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSavedVersion(null);
    try {
      const saved = await onSave(scope.scope_id, { read_roots: readRoots, write_roots: writeRoots });
      setSavedVersion(saved.version);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleDiscard = () => {
    setReadText(scope.read_roots.join("\n"));
    setWriteText(scope.write_roots.join("\n"));
    setError(null);
    setSavedVersion(null);
  };

  const textareaStyle: React.CSSProperties = { width: "100%", fontFamily: "monospace", fontSize: "13px" };

  return (
    <div style={{ padding: "12px", background: "var(--bg-primary)", borderRadius: "6px" }}>
      <strong>{scope.name}</strong>
      <span style={{ fontSize: "12px", color: "var(--text-secondary)", marginLeft: "8px" }}>versión {scope.version}</span>

      <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: "6px 0 10px 0" }}>
        Una carpeta por línea. Deben ser rutas absolutas y existentes, por ejemplo{" "}
        <code>C:\Users\usuario\Documentos\proyecto</code>. Los cambios aplican a las tareas nuevas.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
        <label style={{ fontSize: "13px" }}>
          <span style={{ display: "block", fontWeight: "bold", marginBottom: "4px" }}>Carpetas de lectura</span>
          <textarea
            rows={3}
            value={readText}
            onChange={(e) => {
              setReadText(e.target.value);
              setSavedVersion(null);
            }}
            style={textareaStyle}
            disabled={saving}
          />
        </label>
        <label style={{ fontSize: "13px" }}>
          <span style={{ display: "block", fontWeight: "bold", marginBottom: "4px" }}>Carpetas de escritura</span>
          <textarea
            rows={3}
            value={writeText}
            onChange={(e) => {
              setWriteText(e.target.value);
              setSavedVersion(null);
            }}
            style={textareaStyle}
            disabled={saving}
          />
        </label>
      </div>

      <div style={{ fontSize: "13px", marginTop: "8px" }}>Apps: {scope.allowed_apps.join(", ") || "Todas"}</div>

      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "10px" }}>
        <button className="btn-primary" onClick={handleSave} disabled={!isDirty || saving}>
          {saving ? "Guardando..." : "Guardar carpetas"}
        </button>
        <button className="btn-secondary" onClick={handleDiscard} disabled={!isDirty || saving}>
          Descartar
        </button>
        {error && <span style={{ fontSize: "13px", color: "var(--warning)" }}>{error}</span>}
        {savedVersion !== null && !error && (
          <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>✅ Guardado (versión {savedVersion})</span>
        )}
      </div>
    </div>
  );
};
