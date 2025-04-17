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

# 安装基本必要依赖
RUN pip install --no-cache-dir \
    qdrant-client==1.13.3 \
    openai \
    numpy \
    loguru \
    sqlalchemy \
    requests \
    python-dotenv \
    PyYAML \
    cryptography \
    tiktoken \
    pydantic \
    aiohttp \
    fastapi \
    uvicorn

# 复制应用代码
COPY . /app/

# 自动生成Linux环境适用的requirements.txt
RUN cd /app && \
    python -c "import pkg_resources; print('\n'.join(['%s==%s' % (i.key, i.version) for i in pkg_resources.working_set]))" > requirements_base.txt && \
    pip install --no-cache-dir -r /app/linjing/requirements.txt || echo "使用已安装的基础包" && \
    python -c "import pkg_resources; print('\n'.join(['%s==%s' % (i.key, i.version) for i in pkg_resources.working_set]))" > requirements_linux.txt

# 设置启动命令
CMD ["python", "linjing/main.py"] 