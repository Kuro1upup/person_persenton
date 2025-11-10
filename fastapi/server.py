import uvicorn
import argparse
from dotenv import load_dotenv
import os

# 加载.env文件
load_dotenv()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the FastAPI server")
    parser.add_argument(
        "--port", type=int, default=9204, help="Port number to run the server on"
    )
    parser.add_argument(
        "--reload", type=str, default="false", help="Reload the server on code changes"
    )
    args = parser.parse_args()
    reload = args.reload == "true"
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=args.port,
        log_level="info",
        reload=reload,
        # 添加以下超时参数以避免默认的30秒超时
        timeout_keep_alive=60,  # 保持连接活跃的超时时间(秒)
        timeout_graceful_shutdown=300,  # 优雅关闭的超时时间(秒)
    )
