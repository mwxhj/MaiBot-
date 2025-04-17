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

# 复制应用代码 - 从MaiBot-目录复制到容器的/app目录
COPY MaiBot-/ /app/

# 配置文件会通过volume挂载，这里只提供默认配置作为后备
# 只有在挂载的配置不存在时才会使用此默认配置
RUN if [ ! -f /app/config.yaml ]; then \
    echo '# 默认配置文件 - 将被挂载的外部配置覆盖\n\
bot:\n\
  name: "灵境"\n\
  version: "1.0.0"\n\
vector_db:\n\
  type: "qdrant"\n\
  local: true\n\
  local_path: "/app/data/qdrant_db"\n\
  collection_name: "linjing_vectors"\n\
  vector_size: 1536\n\
database:\n\
  type: "sqlite"\n\
  path: "/app/data/linjing.db"' > /app/config.yaml; \
    fi

# 设置启动命令
CMD ["python", "main.py"]