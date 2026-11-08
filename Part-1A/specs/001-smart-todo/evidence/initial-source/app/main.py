from fastapi import FastAPI

from app.api.routes import router
from app.database import database_manager
from app.logging import configure_logging

configure_logging()

database_manager.initialize()

app = FastAPI(title="Smart Todo Application")
app.include_router(router)
