import logging

from fastapi import FastAPI, Request

from app.api.routes import router
from app.database import database_manager
from app.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

database_manager.initialize()

app = FastAPI(title="Smart Todo Application")
app.include_router(router)


@app.middleware("http")
async def log_http_request(request: Request, call_next):
    response = await call_next(request)
    logger.info(
        "HTTP request completed",
        extra={
            "event": "http.request.completed",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
        },
    )
    return response
