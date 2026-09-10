import React from "react";
import { Task } from "../types";

interface HistoryViewProps {
  tasks: Task[];
  onSelectTask: (taskId: string) => void;
}

export const HistoryView: React.FC<HistoryViewProps> = ({ tasks, onSelectTask }) => {
  return (
    <div style={{ maxWidth: 1000, margin: "24px auto" }}>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Historial Local de Tareas</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
          Registro inmutable de todas las tareas delegadas al agente, sus estados finales, evidencias y errores.
        </p>

        {tasks.length === 0 ? (
          <p style={{ color: "var(--text-secondary)" }}>No hay tareas registradas aún.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {tasks.map((t) => (
              <div
                key={t.task_id}
                onClick={() => onSelectTask(t.task_id)}
                style={{
                  padding: "16px",
                  background: "var(--bg-primary)",
                  borderRadius: "8px",
                  border: "1px solid var(--border)",
                  cursor: "pointer",
                  transition: "border-color 0.2s ease",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span className={`badge badge-${t.state}`}>{t.state}</span>
                  <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                    {new Date(t.created_at).toLocaleString()}
                  </span>
                </div>
                <div style={{ fontWeight: "600", fontSize: "15px", marginBottom: "6px" }}>
                  {t.instruction}
                </div>
                <div style={{ display: "flex", gap: "16px", fontSize: "12px", color: "var(--text-secondary)" }}>
                  <span>Pasos: {t.steps_count}</span>
                  <span>Duración activa: {t.active_duration_seconds.toFixed(1)}s</span>
                  {t.output_name && <span>Salida esperada: {t.output_name}</span>}
                </div>
                {t.error_message && (
                  <div style={{ marginTop: "6px", color: "var(--danger)", fontSize: "12px" }}>
                    Error: {t.error_message}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
