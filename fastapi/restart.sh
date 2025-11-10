#!/bin/bash

# 定义虚拟环境目录路径
VENV_DIR="myenv"
# 定义服务端口
PORT=9204
# 定义日志文件路径
LOG_DIR="logs"
LOG_FILE="${LOG_DIR}/presonton.log"
# 定义备份日志目录
BAK_DIR="${LOG_DIR}/bak"

# 查找并停止正在运行的FastAPI服务进程
echo "正在查找并停止现有的FastAPI服务进程..."

# 查找在指定端口运行的Python进程
PID=$(lsof -i :$PORT -t 2>/dev/null)

if [ -n "$PID" ]; then
    echo "找到运行在端口 $PORT 的进程，PID: $PID"
    echo "正在停止进程..."
    kill -15 "$PID"
    
    # 等待进程终止，最多等待5秒
    COUNTER=0
    while ps -p "$PID" > /dev/null && [ $COUNTER -lt 5 ]; do
        echo "等待进程终止... ($COUNTER/5)"
        sleep 1
        COUNTER=$((COUNTER+1))
    done
    
    # 检查进程是否仍在运行
    if ps -p "$PID" > /dev/null; then
        echo "强制终止进程..."
        kill -9 "$PID"
    else
        echo "进程已成功停止"
    fi
else
    echo "未找到运行在端口 $PORT 的进程，可能服务未运行"
fi

# 检查虚拟环境是否存在
if [ ! -d "$VENV_DIR" ]; then
    echo "虚拟环境 $VENV_DIR 不存在，正在创建..."
    python -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "错误：创建虚拟环境失败！请确保已安装Python 3.10+"
        exit 1
    fi
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source "$VENV_DIR/bin/activate"

# 检查激活是否成功
if [ $? -ne 0 ]; then
    echo "错误：激活虚拟环境失败！"
    exit 1
fi

# 可选：更新依赖
# echo "更新依赖..."
# pip install -e .

# 确保日志目录存在
if [ ! -d "$LOG_DIR" ]; then
    echo "日志目录 $LOG_DIR 不存在，正在创建..."
    mkdir -p "$LOG_DIR"
    if [ $? -ne 0 ]; then
        echo "错误：创建日志目录失败！"
        exit 1
    fi
fi

# 备份旧日志文件
if [ -f "$LOG_FILE" ]; then
    echo "备份旧日志文件..."
    # 确保备份目录存在
    if [ ! -d "$BAK_DIR" ]; then
        echo "备份目录 $BAK_DIR 不存在，正在创建..."
        mkdir -p "$BAK_DIR"
        if [ $? -ne 0 ]; then
            echo "错误：创建备份目录失败！"
            exit 1
        fi
    fi
    # 获取日志文件名（不包含路径）
    LOG_FILENAME=$(basename "$LOG_FILE")
    # 移动到备份目录，保留日期时间戳
    mv "$LOG_FILE" "${BAK_DIR}/${LOG_FILENAME}.bak.$(date +%Y%m%d%H%M%S)"
fi

# 重新启动FastAPI服务器
echo "重新启动FastAPI服务..."
nohup python server.py --port $PORT > $LOG_FILE 2>&1 &

# 检查服务是否启动成功
echo "等待服务启动..."
# 定义最大重试次数和每次重试间隔时间
MAX_RETRIES=5
RETRY_INTERVAL=3

# 初始化成功标志
SUCCESS=false

for ((i=1; i<=$MAX_RETRIES; i++)); do
    echo "检查服务状态 (尝试 $i/$MAX_RETRIES)..."
    
    # 方法1: 通过端口检查进程
    PORT_PID=$(lsof -i :$PORT -t 2>/dev/null)
    
    # 方法2: 通过进程名称检查
    PROCESS_PID=$(ps -ef | grep "python server.py --port $PORT" | grep -v grep | awk '{print $2}' 2>/dev/null)
    
    # 如果任一方法检测到了进程ID，则认为服务已启动
    if [ -n "$PORT_PID" ] || [ -n "$PROCESS_PID" ]; then
        # 使用非空的那个PID
        NEW_PID=${PORT_PID:-$PROCESS_PID}
        echo "服务重启成功，新进程PID: $NEW_PID，运行端口 $PORT，日志已输出到 $LOG_FILE"
        SUCCESS=true
        break
    fi
    
    # 如果不是最后一次尝试，则等待并重试
    if [ $i -lt $MAX_RETRIES ]; then
        echo "服务尚未启动，$RETRY_INTERVAL 秒后重试..."
        sleep $RETRY_INTERVAL
    fi
done

# 如果所有尝试都失败，则显示警告
if [ "$SUCCESS" = false ]; then
    echo "警告：服务可能未成功启动，请检查 $LOG_FILE 以获取详细信息"
    # 可选：显示最新的日志内容帮助排查问题
    echo "最近的日志内容："
    tail -n 20 "$LOG_FILE" 2>/dev/null
fi