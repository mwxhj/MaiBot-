# Dockerfile for LinjingBot
# 基于Python 3.9稳定版镜像
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
    && rm -rf /var/lib/apt/lists/*

# 创建用于存储数据和日志的目录
RUN mkdir -p /app/data /app/logs

# 首先复制requirements.txt以利用Docker缓存机制
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装Qdrant客户端，确保使用兼容版本
RUN pip install --no-cache-dir qdrant-client==1.13.3

# 复制应用代码 - 从当前目录复制到容器的/app目录
COPY . /app/

# 设置启动命令
CMD ["python", "main.py"]