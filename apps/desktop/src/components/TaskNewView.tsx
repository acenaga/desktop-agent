import React, { useState } from "react";
import { TaskScope } from "../types";

interface TaskNewViewProps {
  scopes: TaskScope[];
  onSubmitTask: (data: { instruction: string; scope_id: string; input_refs: string[]; output_name?: string }) => void;
}

export const TaskNewView: React.FC<TaskNewViewProps> = ({ scopes, onSubmitTask }) => {
  const [instruction, setInstruction] = useState("");
  const [selectedScope, setSelectedScope] = useState(scopes[0]?.scope_id || "default_scope");
  const [inputRefs, setInputRefs] = useState("");
  const [outputName, setOutputName] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!instruction.trim()) return;

    const refs = inputRefs
      .split("\n")
      .map((r) => r.trim())
      .filter((r) => r.length > 0);

    onSubmitTask({
      instruction,
      scope_id: selectedScope,
      input_refs: refs,
      output_name: outputName.trim() || undefined,
    });
  };

  const loadDemo = (uc: "uc01" | "uc02" | "uc03") => {
    if (uc === "uc01") {
      setInstruction("Compara estas dos propuestas y guarda las diferencias en mi carpeta de salida.");
      setInputRefs("fixtures/uc01/propuesta_alfa.md\nfixtures/uc01/propuesta_beta.docx");
      setOutputName("comparacion_propuestas.md");
    } else if (uc === "uc02") {
      setInstruction("Abre el Bloc de notas, escribe este texto y guárdalo como nota.txt en la carpeta autorizada.");
      setInputRefs("");
      setOutputName("nota.txt");
    } else if (uc === "uc03") {
      setInstruction("Completa este formulario de prueba con los datos que te indico.");
      setInputRefs("http://127.0.0.1:8765/");
      setOutputName("");
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "24px auto" }}>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Nueva Tarea para el Agente Local</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
          Escribe la tarea que deseas delegar en lenguaje natural (español). El agente la ejecutará de forma 100% local, observando y verificando cada paso.
        </p>

        {/* Demostraciones precargadas según Sección 12 */}
        <div style={{ margin: "16px 0", padding: "12px", background: "var(--bg-primary)", borderRadius: "6px" }}>
          <span style={{ fontSize: "12px", fontWeight: "bold", color: "var(--text-secondary)", display: "block", marginBottom: "8px" }}>
            DEMOSTRACIONES CON DATOS SINTÉTICOS:
          </span>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            <button type="button" className="btn-secondary" onClick={() => loadDemo("uc01")}>
              📄 UC-01: Comparar propuestas (Docs)
            </button>
            <button type="button" className="btn-secondary" onClick={() => loadDemo("uc02")}>
              📝 UC-02: Control Bloc de notas (Escritorio)
            </button>
            <button type="button" className="btn-secondary" onClick={() => loadDemo("uc03")}>
              🌐 UC-03: Llenar formulario (Navegador)
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontWeight: "bold", marginBottom: "6px", fontSize: "14px" }}>
              Instrucción para el Agente:
            </label>
            <textarea
              rows={4}
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Ejemplo: Compara las dos propuestas de presupuesto y extrae las diferencias en un reporte markdown."
              required
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
            <div>
              <label style={{ display: "block", fontWeight: "bold", marginBottom: "6px", fontSize: "14px" }}>
                Carpeta o Alcance Autorizado:
              </label>
              <select value={selectedScope} onChange={(e) => setSelectedScope(e.target.value)}>
                {scopes.length > 0 ? (
                  scopes.map((s) => (
                    <option key={s.scope_id} value={s.scope_id}>
                      {s.name} ({s.read_roots.length} lectura / {s.write_roots.length} salida)
                    </option>
                  ))
                ) : (
                  <option value="default_scope">Alcance por Defecto</option>
                )}
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontWeight: "bold", marginBottom: "6px", fontSize: "14px" }}>
                Nombre de Archivo de Salida (Opcional):
              </label>
              <input
                type="text"
                value={outputName}
                onChange={(e) => setOutputName(e.target.value)}
                placeholder="Ejemplo: comparacion.md o nota.txt"
              />
            </div>
          </div>

          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontWeight: "bold", marginBottom: "6px", fontSize: "14px" }}>
              Archivos o Referencias de Entrada (Uno por línea):
            </label>
            <textarea
              rows={2}
              value={inputRefs}
              onChange={(e) => setInputRefs(e.target.value)}
              placeholder="Ej: ./documentos/propuestaA.pdf"
            />
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button type="submit" className="btn-primary" style={{ padding: "10px 24px", fontSize: "15px" }}>
              ▶️ Iniciar Tarea
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
