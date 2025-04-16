#!/bin/bash
set -e

# 输出彩色日志
function log_info() {
    echo -e "\033[0;32m[INFO]\033[0m $1"
}

function log_warn() {
    echo -e "\033[0;33m[WARN]\033[0m $1"
}

function log_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

# 显示欢迎信息
log_info "欢迎使用 MaiBot"
log_info "容器启动中..."

# 检查环境变量
if [ -z "$MONGODB_URI" ]; then
    log_warn "MONGODB_URI 环境变量未设置，使用默认配置"
fi

if [ -z "$NAPCAT_API_BASE" ]; then
    log_warn "NAPCAT_API_BASE 环境变量未设置，使用默认配置"
fi

# 等待依赖服务启动
log_info "等待依赖服务启动..."

# 等待MongoDB可用
wait_for_mongodb() {
    local host
    host=$(echo $MONGODB_URI | sed -E 's/.*@([^:]+).*/\1/')
    if [ "$host" = "$MONGODB_URI" ]; then
        host="mongodb"
    fi
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        attempt=$((attempt+1))
        log_info "尝试连接 MongoDB ($attempt/$max_attempts)..."
        if nc -z $host 27017; then
            log_info "MongoDB 已就绪"
            return 0
        fi
        sleep 2
    done
    
    log_error "无法连接到 MongoDB，超过最大尝试次数"
    return 1
}

# 等待Redis可用
wait_for_redis() {
    local host="redis"
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        attempt=$((attempt+1))
        log_info "尝试连接 Redis ($attempt/$max_attempts)..."
        if nc -z $host 6379; then
            log_info "Redis 已就绪"
            return 0
        fi
        sleep 2
    done
    
    log_error "无法连接到 Redis，超过最大尝试次数"
    return 1
}

# 初始化数据目录
init_directories() {
    log_info "初始化数据目录..."
    mkdir -p /app/logs
    mkdir -p /app/data
    mkdir -p /app/config
    
    # 确保日志目录可写
    chmod -R 755 /app/logs
    
    # 如果配置文件不存在，则创建默认配置
    if [ ! -f /app/config/default_config.json ]; then
        log_info "创建默认配置文件..."
        mkdir -p /app/config
        echo '{}' > /app/config/default_config.json
    fi
}

# 信号处理函数
handle_sigterm() {
    log_info "收到关闭信号，优雅关闭中..."
    # 在这里可以添加额外的清理操作
    exit 0
}

# 注册信号处理器
trap handle_sigterm SIGTERM SIGINT

# 主函数
main() {
    init_directories
    
    # 等待依赖服务
    wait_for_mongodb
    wait_for_redis
    
    # 显示环境信息
    log_info "启动 MaiBot 服务，环境: ${LOG_LEVEL:-INFO}"
    
    # 启动应用
    log_info "启动 MaiBot 主程序..."
    
    if [ "$DEBUG" = "true" ]; then
        log_info "以调试模式运行"
        exec python -u /app/main.py
    else
        exec python -u /app/main.py
    fi
}

# 如果脚本被直接执行（而不是被导入）
if [ "$1" = "" ]; then
    main
else
    # 如果提供了参数，则执行指定的命令
    exec "$@"
fi 