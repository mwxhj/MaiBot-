# 林静 (Linjing) - AI聊天机器人

林静是一个拥有个性的AI聊天机器人，支持情绪系统、记忆系统和多种交互方式。

## 特性

- 📝 **记忆系统**：记住并回忆过去的对话和重要事件
- 😊 **情绪系统**：根据交互动态调整情绪状态
- 🧠 **多维人格**：可配置的人格特质
- 🔌 **插件支持**：易于扩展的插件系统
- 💬 **多平台支持**：通过适配器支持不同的通讯平台

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/username/linjing.git
cd linjing

# 安装依赖
pip install -e .
```

### 配置

1. 复制示例配置文件：
```bash
cp config/default_config.json config/user_config.json
```

2. 编辑 `config/user_config.json` 并填入必要的API密钥和配置

### 运行

```bash
python -m linjing.main
```

## 开发指南

### 项目结构

```
linjing/                      # 主项目目录
├── main.py                   # 主程序入口
├── config.py                 # 全局配置管理
├── constants.py              # 常量定义
├── bot/                      # 机器人核心
├── adapters/                 # 适配器层
├── processors/               # 处理器模块
├── memory/                   # 记忆系统
├── emotion/                  # 情绪系统
├── storage/                  # 数据存储
├── llm/                      # LLM接口
├── plugins/                  # 插件系统
├── utils/                    # 工具类
└── config/                   # 配置文件
```

### 添加新插件

插件可以扩展机器人的功能。创建新插件只需要：

1. 在 `plugins` 目录下创建新的Python文件
2. 继承 `Plugin` 基类
3. 实现必要的方法
4. 在配置文件中启用插件

## 许可证

MIT 