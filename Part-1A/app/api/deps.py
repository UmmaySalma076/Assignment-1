from app.database import get_database_manager
from app.services.task_service import TaskService


def get_task_service() -> TaskService:
    manager = get_database_manager()
    manager.initialize()
    return manager.task_service
