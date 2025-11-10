from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.lifespan import app_lifespan
from api.middlewares.user_config_middleware import UserConfigEnvUpdateMiddleware
from api.middlewares.auth_middleware import AuthMiddleware
from api.v1.ppt.router import API_V1_PPT_ROUTER
from api.v1.webhook.router import API_V1_WEBHOOK_ROUTER
from api.v1.mock.router import API_V1_MOCK_ROUTER
from api.v1.auth.router import AUTH_ROUTER
from utils.error_handling import register_exception_handlers
import os

app = FastAPI(lifespan=app_lifespan)

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 挂载app_data/images目录，用于前端访问生成的图片
app_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app_data")
if os.path.exists(app_data_dir):
    app.mount("/app_data", StaticFiles(directory=app_data_dir), name="app_data")

# Routers
app.include_router(API_V1_PPT_ROUTER)
app.include_router(API_V1_WEBHOOK_ROUTER)
app.include_router(API_V1_MOCK_ROUTER)
app.include_router(AUTH_ROUTER)

# Middlewares
origins = [
    "http://localhost:9201",
    "http://localhost:9203",
    "http://localhost:9205",   
    "https://slides.comparegpt.io/",
    # 如果您有其他前端环境，也可以在这里添加，
    # 例如生产环境的域名 "https://your-production-domain.com"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(UserConfigEnvUpdateMiddleware)
app.add_middleware(AuthMiddleware)

# 注册全局异常处理器
register_exception_handlers(app)
