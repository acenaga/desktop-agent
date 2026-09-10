"""
core/exceptions.py: Excepciones tipadas del motor del agente.
"""

class AgentCoreError(Exception):
    def __init__(self, message: str, code: str = "CORE_ERROR"):
        super().__init__(message)
        self.code = code
        self.message = message


class TaskCancelledError(AgentCoreError):
    def __init__(self, message: str = "La tarea fue cancelada por el usuario o sistema."):
        super().__init__(message, code="TASK_CANCELLED")


class TaskLimitExceededError(AgentCoreError):
    def __init__(self, message: str):
        super().__init__(message, code="LIMIT_EXCEEDED")


class NoProgressError(AgentCoreError):
    def __init__(self, message: str = "Se detectaron 3 acciones consecutivas sin avance observable."):
        super().__init__(message, code="NO_PROGRESS")
