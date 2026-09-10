import React, { useEffect, useState, useRef } from "react";
import { Navbar } from "./components/Navbar";
import { TaskNewView } from "./components/TaskNewView";
import { TaskExecutionView } from "./components/TaskExecutionView";
import { HistoryView } from "./components/HistoryView";
import { SettingsView } from "./components/SettingsView";
import { ApprovalModal } from "./components/ApprovalModal";
import { api, setApiConfig } from "./api/client";
import { HealthStatus, ModelItem, Task, Action, Artifact, TaskScope, TaskEvent } from "./types";

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<"new" | "execution" | "history" | "settings">("new");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [models, setModels] = useState<ModelItem[]>([]);
  const [scopes, setScopes] = useState<TaskScope[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [actions, setActions] = useState<Action[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [isInteracting, setIsInteracting] = useState(false);

  // Estado del modal de aprobación
  const [pendingApproval, setPendingApproval] = useState<{
    approvalId: string;
    summary: string;
    argumentsData: Record<string, any>;
  } | null>(null);

  const cleanupSseRef = useRef<(() => void) | null>(null);

  // Inicialización
  useEffect(() => {
    // Configuración inicial de API local
    setApiConfig("http://127.0.0.1:8000", "");

    loadInitialData();

    // Atajo global de emergencia (Ctrl+Alt+Esc) según Sección 7.2
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.altKey && e.key === "Escape") {
        if (activeTask && !["completed", "failed", "cancelled"].includes(activeTask.state)) {
          console.warn("[EMERGENCY STOP] Detención activada por Ctrl+Alt+Esc");
          api.cancelTask(activeTask.task_id).catch(console.error);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeTask]);

  const loadInitialData = async () => {
    try {
      const h = await api.getHealth();
      setHealth(h);
      const m = await api.getModels();
      setModels(m.models);
      const s = await api.listScopes();
      setScopes(s);
      const t = await api.listTasks();
      setTasks(t);

      // Si hay una tarea en ejecución, activarla
      const running = t.find((task) => ["running", "paused", "awaiting_approval", "queued"].includes(task.state));
      if (running) {
        selectTask(running.task_id);
      }
    } catch (err) {
      console.warn("No se pudo conectar al servicio local de inmediato:", err);
    }
  };

  const selectTask = async (taskId: string) => {
    try {
      const detail = await api.getTask(taskId);
      setActiveTask(detail.task);
      setActions(detail.actions);
      setArtifacts(detail.artifacts);
      setCurrentTab("execution");

      // Conectar SSE si la tarea está viva
      if (cleanupSseRef.current) {
        cleanupSseRef.current();
      }

      if (!["completed", "failed", "cancelled", "interrupted"].includes(detail.task.state)) {
        cleanupSseRef.current = api.connectEvents(
          taskId,
          (event) => handleIncomingEvent(event, taskId),
          (err) => console.error("SSE Error:", err)
        );
      }
    } catch (err) {
      console.error("Error al cargar tarea:", err);
    }
  };

  const handleIncomingEvent = (event: TaskEvent, taskId: string) => {
    setEvents((prev) => [...prev, event]);

    // Actualizar estado del indicador de interacción
    if (event.event_type === "action_started") {
      const tool = event.payload.tool || "";
      if (tool.startsWith("desktop.") || tool.startsWith("browser.")) {
        setIsInteracting(true);
      }
    } else if (event.event_type === "action_completed" || event.event_type === "action_failed") {
      setIsInteracting(false);
    }

    if (event.event_type === "approval_requested") {
      setPendingApproval({
        approvalId: event.payload.approval_id,
        summary: event.payload.summary,
        argumentsData: event.payload.arguments,
      });
    }

    // Refrescar estado completo de la tarea
    api.getTask(taskId).then((detail) => {
      setActiveTask(detail.task);
      setActions(detail.actions);
      setArtifacts(detail.artifacts);
      if (["completed", "failed", "cancelled", "interrupted"].includes(detail.task.state)) {
        setIsInteracting(false);
      }
    }).catch(console.error);
  };

  const handleCreateTask = async (data: {
    instruction: string;
    scope_id: string;
    input_refs: string[];
    output_name?: string;
  }) => {
    try {
      const res = await api.createTask(data);
      await selectTask(res.task_id);
      loadInitialData();
    } catch (err: any) {
      alert(`Error al crear la tarea: ${err.message}`);
    }
  };

  const handlePause = async () => {
    if (activeTask) {
      await api.pauseTask(activeTask.task_id);
    }
  };

  const handleResume = async () => {
    if (activeTask) {
      await api.resumeTask(activeTask.task_id);
    }
  };

  const handleCancel = async () => {
    if (activeTask) {
      await api.cancelTask(activeTask.task_id);
    }
  };

  const handleResolveApproval = async (approved: boolean) => {
    if (activeTask && pendingApproval) {
      await api.resolveApproval(activeTask.task_id, pendingApproval.approvalId, approved);
      setPendingApproval(null);
    }
  };

  return (
    <div>
      <Navbar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        health={health}
        isInteracting={isInteracting}
      />

      <main style={{ padding: "0 16px" }}>
        {currentTab === "new" && (
          <TaskNewView scopes={scopes} onSubmitTask={handleCreateTask} />
        )}
        {currentTab === "execution" && (
          <TaskExecutionView
            task={activeTask}
            actions={actions}
            artifacts={artifacts}
            events={events}
            onPause={handlePause}
            onResume={handleResume}
            onCancel={handleCancel}
          />
        )}
        {currentTab === "history" && (
          <HistoryView tasks={tasks} onSelectTask={selectTask} />
        )}
        {currentTab === "settings" && (
          <SettingsView
            health={health}
            models={models}
            scopes={scopes}
            onRefreshModels={loadInitialData}
            onSavePreference={(k, v) => api.setPreference(k, v)}
          />
        )}
      </main>

      {/* Modal de Aprobación */}
      {pendingApproval && (
        <ApprovalModal
          approvalId={pendingApproval.approvalId}
          summary={pendingApproval.summary}
          argumentsData={pendingApproval.argumentsData}
          onResolve={handleResolveApproval}
        />
      )}
    </div>
  );
};
