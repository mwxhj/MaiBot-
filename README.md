# MaiBot - 灵境大语言模型交互系统

MaiBot是一个支持多种大语言模型的交互系统，提供了统一的接口来访问和管理各种LLM提供商，如OpenAI和Azure OpenAI服务。

## 主要功能

- 多提供商支持：同时管理多个AI服务提供商
- 自动故障切换：当一个提供商不可用时自动切换到备用提供商
- 基于任务的路由：根据不同任务类型选择最合适的模型
- 令牌计数和管理：精确计算不同模型的令牌使用情况
- 提示词模板：支持条件逻辑和循环的高级提示词模板系统
- 内存和向量存储：存储对话历史和嵌入向量的系统

## 安装

### 环境要求

- Python 3.8+ 
- pip包管理工具

### 安装步骤

1. 克隆仓库

```bash
git clone https://github.com/yourusername/MaiBot.git
cd MaiBot
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

MaiBot通过`config.yaml`文件进行配置。以下是主要配置部分的说明：

### 配置LLM提供商

```yaml
llm:
  # 默认使用的提供商ID
  default_provider: "openai_default"
  
  # 令牌计数器设置
  token_counter:
    default_model: "gpt-3.5-turbo"
  
  # 提供商配置列表
  providers:
    # 官方OpenAI API
    - id: "openai_default"
      type: "openai"
      name: "OpenAI官方API"
      enabled: true
      model: "gpt-3.5-turbo"
      api_key: "your-openai-api-key"  # 替换为你的OpenAI API密钥
      api_base: "https://api.openai.com/v1"
      organization: ""  # 可选，组织ID
      timeout: 30
      max_retries: 3
      retry_delay: 1
      embedding_model: "text-embedding-3-small"
```

你可以添加多个提供商，每个提供商需要一个唯一的`id`：

- `openai`类型的提供商需要设置`api_key`、`model`和可选的`api_base`（对于自定义或代理API端点）
- `azure`类型的提供商需要设置`api_key`、`resource_name`和`deployment_name`

### 配置任务路由

```yaml
usage_strategy:
  # 当一个提供商达到错误阈值或超时时，自动切换到下一个可用提供商
  auto_fallback: true
  # 根据不同任务使用不同提供商
  task_routing:
    chat: "openai_default"
    embeddings: "openai_default"
    summarization: "openai_default"
    creative: "openai_default"
```

### 配置存储

```yaml
storage:
  # SQLite数据库设置
  database:
    db_path: "data/linjing.db"
    
  # 向量数据库设置 (Qdrant)
  vector_db:
    collection_name: "memories"
    vector_size: 1536  # OpenAI嵌入向量维度
    similarity: "cosine"  # 相似度计算方法: cosine, euclid, dot
    location: "data/vector_db"  # 本地存储路径
```

## 使用示例

以下是使用MaiBot的简单示例：

```python
import asyncio
from linjing.llm import LLMManager
import yaml

# 加载配置
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

async def main():
    # 初始化LLM管理器
    llm_manager = LLMManager(config)
    await llm_manager.initialize()
    
    # 生成文本
    prompt = "讲一个关于人工智能的短故事。"
    text, metadata = await llm_manager.generate_text(prompt, max_tokens=500)
    
    print(f"生成的文本: {text}")
    print(f"使用的提供商: {metadata['provider_name']}")
    print(f"令牌使用: {metadata['usage']}")
    
    # 生成嵌入向量
    text_to_embed = "这是一段需要转换为向量的文本"
    embedding, metadata = await llm_manager.generate_embedding(text_to_embed)
    
    print(f"嵌入向量维度: {len(embedding)}")
    
    # 关闭管理器
    await llm_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## 高级功能

### 使用提示词模板

```python
from linjing.llm import PromptTemplate

# 创建模板
template = PromptTemplate(
    """
    你是一个{role}。
    {%if show_instructions%}
    请按照以下说明回答问题: {instructions}
    {%endif%}
    
    用户问题: {question}
    """
)

# 格式化模板
formatted = template.format(
    role="医疗顾问",
    show_instructions=True,
    instructions="简明扼要地回答，使用专业术语",
    question="什么是高血压？"
)
```

### 令牌计数

```python
from linjing.llm import TokenCounter

counter = TokenCounter("gpt-3.5-turbo")
text = "这是一段示例文本，用于计算令牌数。"

# 计算令牌数
tokens = counter.count_tokens(text)
print(f"令牌数: {tokens}")

# 消息令牌计数
messages = [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "有什么可以帮助你的？"}
]
total, details = counter.count_message_tokens(messages)
print(f"总令牌数: {total}")
```

## 贡献

欢迎提交问题报告和功能请求！如果你想贡献代码，请先创建一个issue描述你的想法。

## 许可证

本项目采用MIT许可证。详见LICENSE文件。 