# MaiBot Docker 部署指南

本指南将帮助您使用 Docker 和 Docker Compose 部署 MaiBot。

## 前提条件

- 安装 [Docker](https://docs.docker.com/get-docker/)
- 安装 [Docker Compose](https://docs.docker.com/compose/install/)

## 快速开始

### 1. 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑环境变量文件，修改为您的配置
nano .env
```

### 2. 启动服务

```bash
# 在项目根目录下运行
docker-compose -f docker/docker-compose.yml up -d
```

### 3. 查看日志

```bash
# 查看所有服务的日志
docker-compose -f docker/docker-compose.yml logs -f

# 只查看 MaiBot 的日志
docker-compose -f docker/docker-compose.yml logs -f maibot
```

### 4. 停止服务

```bash
docker-compose -f docker/docker-compose.yml down
```

## 服务说明

- **maibot**: MaiBot 主服务，处理消息和逻辑
- **mongodb**: 数据库服务，存储聊天记录和记忆
- **redis**: 缓存服务，用于高速数据缓存
- **napcat**: OneBot 实现，负责与聊天平台通信

## 数据卷

- **mongodb_data**: MongoDB 数据
- **redis_data**: Redis 数据
- **napcat_data**: napcat 配置和数据

## 端口映射

- **8080**: MaiBot WebSocket 端口
- **8081**: MaiBot HTTP API 端口
- **27017**: MongoDB 端口
- **6379**: Redis 端口
- **3000**: napcat 端口

## 自定义配置

您可以通过修改环境变量文件（`.env`）来自定义配置。主要配置包括：

- 数据库连接信息
- API 密钥
- 服务端口
- napcat 配置

## 常见问题

### 1. 如何检查容器状态？

```bash
docker-compose -f docker/docker-compose.yml ps
```

### 2. 如何重启单个服务？

```bash
docker-compose -f docker/docker-compose.yml restart maibot
```

### 3. 数据持久化在哪里？

默认情况下，Docker 会创建命名卷来存储数据。这些卷在容器删除后依然存在。

要查看所有卷：

```bash
docker volume ls
``` 