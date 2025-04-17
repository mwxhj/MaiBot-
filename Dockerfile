# Dockerfile for LinjingBot
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LINJING_DATA_DIR=/app/data \
    LINJING_ENV=production

# 安装系统依赖和基础工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 创建用于存储数据和日志的目录
RUN mkdir -p /app/data /app/logs

# 复制应用代码
COPY . /app/

# 直接安装所需依赖，不使用requirements.txt
RUN pip install --no-cache-dir \
    qdrant-client==1.13.3 \
    openai \
    numpy \
    pandas \
    pydantic \
    sqlalchemy \
    requests \
    python-dotenv \
    PyYAML \
    fastapi \
    uvicorn \
    websockets \
    aiohttp \
    asyncio \
    typing-extensions \
    pillow

# 设置启动命令 - 使用正确的入口点
CMD ["python", "linjing/main.py"] 