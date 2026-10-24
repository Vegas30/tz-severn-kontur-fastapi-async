from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.init_db import create_first_admin
from app.db.session import create_db_and_tables, engine
from app.routers import access, auditlog, auth, documents, projects, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    await create_first_admin()
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Документ-центр API для ИП «Северный Контур»

Внутренний веб-API сервис для управления документами по проектам.

### Возможности:
- **Аутентификация** - JWT токены, bcrypt хеширование паролей
- **Роли** - admin, manager, worker, viewer
- **Проекты** - создание, редактирование, управление доступом
- **Документы** - создание, редактирование, публикация, архивирование
- **Версионирование** - автоматическое сохранение версий документов
- **Аудит** - журнал всех действий пользователей

### Роли:
- **admin** - полный доступ ко всем проектам и пользователям
- **manager** - ведёт проекты, выдаёт доступ участникам своих проектов
- **worker** - читает и редактирует документы в рамках доступа "editor"
- **viewer** - только чтение в рамках выданного доступа
""",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Авторизация идёт через Bearer-токен в заголовке, а не cookie,
# поэтому allow_credentials=False (с "*" в origins credentials=True недопустимо по спецификации CORS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


app.include_router(users.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(access.router)
app.include_router(documents.router)
app.include_router(auditlog.router)
