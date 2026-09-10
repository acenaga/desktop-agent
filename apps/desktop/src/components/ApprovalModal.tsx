import React from "react";

interface ApprovalModalProps {
  approvalId: string;
  summary: string;
  argumentsData: Record<string, any>;
  onResolve: (approved: boolean) => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  approvalId,
  summary,
  argumentsData,
  onResolve,
}) => {
  return (
    <div className="modal-backdrop">
      <div className="modal-content">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0, color: "var(--warning)" }}>⚠️ Aprobación Requerida</h3>
          <span style={{ fontSize: "11px", color: "var(--text-secondary)", fontFamily: "monospace" }}>{approvalId}</span>
        </div>
        <p style={{ fontSize: "14px", lineHeight: "1.5" }}>
          El agente solicita autorización para realizar una acción que modifica recursos existentes.
        </p>

        <div style={{ padding: "12px", background: "var(--bg-primary)", borderRadius: "6px", marginBottom: "16px" }}>
          <strong>Motivo:</strong>
          <div style={{ marginTop: "4px", fontSize: "13px" }}>{summary}</div>
        </div>

        <div style={{ marginBottom: "16px" }}>
          <span style={{ fontSize: "12px", fontWeight: "bold", color: "var(--text-secondary)" }}>
            ARGUMENTOS CANÓNICOS EXACTOS:
          </span>
          <pre style={{
            background: "var(--bg-primary)",
            padding: "10px",
            borderRadius: "6px",
            fontSize: "12px",
            overflowX: "auto",
            marginTop: "6px",
          }}>
            {JSON.stringify(argumentsData, null, 2)}
          </pre>
        </div>

        <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "20px" }}>
          ℹ️ Esta autorización es de un solo uso y aplica estrictamente a los argumentos mostrados.
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
          <button className="btn-danger" onClick={() => onResolve(false)}>
            ❌ Rechazar Acción
          </button>
          <button className="btn-primary" onClick={() => onResolve(true)}>
            ✅ Aprobar y Ejecutar
          </button>
        </div>
      </div>
    </div>
  );
};
