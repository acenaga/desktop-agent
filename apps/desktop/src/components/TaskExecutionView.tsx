import React from "react";
import { Task, Action, Artifact, TaskEvent } from "../types";

interface TaskExecutionViewProps {
  task: Task | null;
  actions: Action[];
  artifacts: Artifact[];
  events: TaskEvent[];
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
}

export const TaskExecutionView: React.FC<TaskExecutionViewProps> = ({
  task,
  actions,
  artifacts,
  events,
  onPause,
  onResume,
  onCancel,
}) => {
  if (!task) {
    return (
      <div style={{ maxWidth: 800, margin: "40px auto", textAlign: "center" }}>
        <div className="card">
          <h3>No hay ninguna tarea activa en ejecución</h3>
          <p style={{ color: "var(--text-secondary)" }}>
            Inicia una nueva tarea desde la pestaña "Nueva Tarea".
          </p>
        </div>
      </div>
    );
  }

  const isPaused = task.state === "paused";
  const isRunning = task.state === "running";
  const isTerminal = ["completed", "failed", "cancelled", "interrupted"].includes(task.state);

  return (
    <div style={{ maxWidth: 1000, margin: "24px auto" }}>
      {/* Cabecera de Estado y Controles */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
              <span className={`badge badge-${task.state}`}>{task.state}</span>
              <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                ID: {task.task_id}
              </span>
            </div>
            <h3 style={{ margin: 0 }}>{task.instruction}</h3>
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            {isRunning && (
              <button className="btn-secondary" onClick={onPause}>
                ⏸️ Pausar
              </button>
            )}
            {isPaused && (
              <button className="btn-primary" onClick={onResume}>
                ▶️ Reanudar
              </button>
            )}
            {!isTerminal && (
              <button className="btn-danger" onClick={onCancel} title="Atajo de emergencia: Ctrl+Alt+Esc">
                🛑 Detener
              </button>
            )}
          </div>
        </div>

        {/* Explicación del plan según Sección 3.1 */}
        {task.plan_explanation && (
          <div style={{ padding: "12px", background: "var(--bg-primary)", borderRadius: "6px", borderLeft: "4px solid var(--accent-primary)", marginBottom: "16px" }}>
            <span style={{ fontSize: "12px", fontWeight: "bold", color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>
              PLAN DE ACCIÓN DEL AGENTE:
            </span>
            <span style={{ fontSize: "14px" }}>{task.plan_explanation}</span>
          </div>
        )}

        <div style={{ display: "flex", gap: "24px", fontSize: "13px", color: "var(--text-secondary)" }}>
          <span>Pasos ejecutados: <strong>{task.steps_count}</strong></span>
          <span>Tiempo activo: <strong>{task.active_duration_seconds.toFixed(1)}s</strong></span>
          <span>Artefactos generados: <strong>{artifacts.length}</strong></span>
          <span>Eventos SSE: <strong>{events.length}</strong></span>
        </div>
      </div>

      {/* Artefactos generados verificados */}
      {artifacts.length > 0 && (
        <div className="card" style={{ borderColor: "var(--success)" }}>
          <h4 style={{ margin: "0 0 12px 0", color: "var(--success)" }}>✅ Archivos Generados y Comprobados</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {artifacts.map((art) => (
              <div
                key={art.artifact_id}
                style={{
                  padding: "10px",
                  background: "var(--bg-primary)",
                  borderRadius: "6px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: "13px",
                }}
              >
                <div>
                  <strong>{art.file_name}</strong>
                  <div style={{ color: "var(--text-secondary)", fontSize: "11px" }}>
                    Ruta: {art.file_path}
                  </div>
                </div>
                <div style={{ textAlign: "right", color: "var(--text-secondary)" }}>
                  <div>{(art.size_bytes / 1024).toFixed(1)} KB</div>
                  <div style={{ fontSize: "10px", fontFamily: "monospace" }}>SHA256: {art.sha256.slice(0, 10)}...</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Acciones y Eventos en Tiempo Real */}
      <div className="card">
        <h4 style={{ margin: "0 0 16px 0" }}>Línea de Tiempo de Acciones</h4>
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "400px", overflowY: "auto" }}>
          {actions.length === 0 ? (
            <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>Esperando primera propuesta del modelo...</p>
          ) : (
            actions.map((act) => (
              <div
                key={act.action_id}
                style={{
                  padding: "12px",
                  background: "var(--bg-primary)",
                  borderRadius: "6px",
                  borderLeft: `4px solid ${
                    act.state === "completed"
                      ? "var(--success)"
                      : act.state === "failed"
                      ? "var(--danger)"
                      : "var(--warning)"
                  }`,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <span style={{ fontWeight: "bold", fontSize: "14px", fontFamily: "monospace" }}>
                    {act.tool}
                  </span>
                  <span className={`badge badge-${act.state}`} style={{ fontSize: "10px" }}>
                    {act.state}
                  </span>
                </div>
                <div style={{ fontSize: "13px", color: "var(--text-primary)", marginBottom: "4px" }}>
                  {act.brief_reason}
                </div>
                {act.error && (
                  <div style={{ fontSize: "12px", color: "var(--danger)", marginTop: "4px" }}>
                    Error: {act.error}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
