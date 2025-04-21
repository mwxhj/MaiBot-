# 林镜 Bot V12 - 5层架构开发指南

**版本:** 1.0

**目标:** 构建一个智能、自适应、具备深度"读空气"能力，且符合 V12 人格和风格指南的 QQ 聊天机器人。

**核心架构:**

1.  **L1: 输入缓冲与快速感知 (Input Buffer & FastSense Processor)**
2.  **L2: 智能分发与资源调度 (Adaptive Dispatcher)**
3.  **L3: 分级思考与决策 (Tiered ThoughtGenerator)**
4.  **L4: 统一风格化与安全检查 (Final Polisher & Guard)**
5.  **L5: 行为执行与反馈收集 (Action Executor & Feedback Loop)**

---

## 一、 先决条件与环境设置

### 1. 技术栈

*   **核心:**
    *   Python 3.9+ (熟练掌握 asyncio 异步编程)
    *   Loguru (日志库)
    *   AIOHTTP, Websockets (用于 OneBot 适配器)
    *   YAML (配置文件)
    *   Docker & Docker Compose (推荐部署方式)
*   **可选 NLP:**
    *   spaCy, NLTK, Hugging Face Transformers (用于 L1 FastSense)
*   **可选规则引擎:**
    *   `experta` (纯 Python), 或考虑集成 Drools 等
*   **可选机器学习:**
    *   Scikit-learn, PyTorch/TensorFlow (用于 L2 分类模型或 L5 学习代理)
*   **可选数据存储:**
    *   数据库: PostgreSQL/SQLite (记忆、状态、反馈)
    *   向量数据库: Qdrant, Milvus, ChromaDB (语义记忆检索)
*   **可选任务调度:**
    *   Celery, APScheduler (用于 L5 延迟响应)

### 2. 基础知识

*   面向对象编程 (OOP)
*   异步 IO (Async/Await)
*   设计模式 (如策略模式、责任链模式)
*   LLM Prompt Engineering
*   Docker 基础 (镜像、容器、网络、卷)
*   基本的 Linux 操作

### 3. 环境准备

*   创建项目目录结构 (e.g., `linjing/`, `config/`, `logs/`, `data/`, `docker/`)。
*   使用 `venv` 或 `conda` 创建独立的 Python 虚拟环境。
*   安装必要的 Python 依赖 (`pip install -r requirements.txt`)。
*   配置好你的开发环境 (IDE, Git)。
*   获取必要的 API Keys (LLMs)。
*   安装并配置 Docker 和 Docker Compose。

---

## 二、 核心实现 (分层迭代)

### Layer 1: 输入缓冲与快速感知

*   **目标**: 高效接收、缓冲消息，执行快速、廉价的基础分析，生成 `routing_assessment`。
*   **关键组件实现**:
    *   `InputBuffer`: 使用 `asyncio.Queue` 和定时/计数逻辑实现缓冲和批处理。
        *   `async add_raw_event(raw_event: dict) -> None`: 添加来自适配器的原始事件。
        *   `async get_batch() -> List[dict]`: (内部) 获取一批待处理的原始事件。
    *   `FastSenseNLPModule`: 实现轻量级 NLP (规则/模型)，处理单条/批量文本。
        *   `async process(text: str) -> dict`: 输入文本，输出基础 NLP 分析结果 (如关键词、情感倾向)。
    *   `LightweightV12TriggerScanner`: 基于配置规则匹配 V12 触发器。
        *   `scan(raw_event: dict) -> List[str]`: 输入原始事件，输出匹配到的 V12 触发器标识列表。
    *   `ContextAggregator`: 从缓存/轻量存储快速获取少量关键上下文。
        *   `async get_summary(session_id: str, user_id: str) -> dict`: 输入会话/用户ID，输出简化的上下文摘要。
    *   `FastSenseProcessor`: 编排 L1 组件，构建 `routing_assessment` JSON。
        *   `async process_event(raw_event: dict) -> dict`: 输入单个原始事件，编排 L1 分析，输出 `routing_assessment` 字典。
*   **`routing_assessment` JSON Schema (核心)**: (需根据实际需求详细定义，包含消息元数据、发送者信息、基础分析结果、V12 触发器扫描、上下文摘要、复杂度/即时性评估等)
*   **测试**: 单元测试各组件，集成测试 L1 完整流程。

### Layer 2: 智能分发与资源调度

*   **目标**: 系统的智能路由核心，根据 L1 评估和全局状态，决定处理路径 (A/B/C/O) 和资源。
*   **关键组件实现**:
    *   `StateMonitorInterface`: 提供接口获取 Bot 全局实时/准实时状态 (负载、模式等)。
        *   `async get_global_state() -> dict`: 输出包含 Bot 状态信息的字典。
    *   `DecisionEngine`: 实现路由决策逻辑 (规则/模型)，输入 L1 评估和全局状态，输出路径和资源建议。
        *   `decide(assessment: dict, global_state: dict) -> dict`: 输入 `routing_assessment` 和全局状态，输出 `dispatch_decision` 字典。
    *   `AdaptiveDispatcher` (L2 主控制器):
        *   `async dispatch(assessment: dict) -> None`: 接收 `routing_assessment`，获取状态，调用 `DecisionEngine`，并将包含 `dispatch_decision` 的任务路由到 L3 对应的处理队列或流程。
*   **`dispatch_decision` JSON Schema (核心)**: (需根据实际需求详细定义，包含选择的路径、目标资源提示、合并/选择后的输入、决策理由等)
*   **测试**: 单元测试决策引擎，集成测试 L2 完整流程。

### Layer 3: 分级思考与决策

*   **目标**: 执行核心思考，深度理解，结合 V12 原则进行决策，生成 `mind_info`。
*   **关键组件实现**:
    *   `Context/MemoryRetriever`: 根据需要从数据库/向量库检索详细上下文和记忆。
        *   `async retrieve(session_id: str, user_id: str, query: str, top_k: int) -> List[str]`: 输入会话/用户ID、检索查询和数量，输出相关文本片段列表。
    *   `PromptAssembler` (**核心难点**): 使用模板引擎 (如 Jinja2) 动态构建包含输入、上下文、记忆、**V12 人格原则 (源自 `config/personality_principles.md`)**、任务指令和输出格式要求的 LLM Prompt。**具体的 Prompt 模板定义在 `config/prompts.yaml` 中，模板内会引用（如通过 `{personality_text}` 变量）人格原则和（可能间接影响思考的）风格指南 (`config/style_guide.md`) 的内容。**
        *   `assemble(prompt_key: str, context_data: dict) -> str`: 输入 Prompt 模板的键名（如 'thought_generator.thinking_prompt'）和包含所有填充变量（包括从 `personality_principles.md` 和 `style_guide.md` 加载的内容）的字典，输出组装好的最终 LLM Prompt 字符串。
    *   `LLMInterfaces`: 封装不同 LLM API 的调用，处理错误和重试。
        *   `async invoke(prompt: str, model_name: str, config: dict) -> dict`: 输入 Prompt、模型名和配置，输出 LLM 返回的结构化数据 (解析后的 JSON)。
    *   `ConcurrencyManager`: 使用 `asyncio.Semaphore` 控制 LLM 并发。
        *   `async acquire() -> None`: (内部) 获取并发许可。
        *   `async release() -> None`: (内部) 释放并发许可。
    *   `TieredThoughtGenerator`: 主控逻辑，根据路径执行不同深度的思考流程，调用 `PromptAssembler` 获取模板，调用 `LLMInterfaces` 执行 LLM，解析并校验 LLM 输出的结构化 `mind_info` JSON。**其核心思考逻辑和决策依据由 `config/personality_principles.md` 中定义的人格原则驱动（通过 `config/prompts.yaml` 中的 `thought_generator.thinking_prompt` 体现）。**
        *   `async generate_thought(dispatch_decision: dict) -> dict`: 输入 `dispatch_decision`，编排 L3 流程，输出最终的 `mind_info` 字典。
*   **`mind_info` JSON Schema (核心)**: (需根据实际需求详细设计，包含处理路径、LLM信息、思考链、最终行动决策、置信度、响应细节、沉默/延迟原因、V12检查结果、成本估算等，**其结构需与 `prompts.yaml` 中的要求保持一致，并反映 `personality_principles.md` 的思考维度**)
*   **`mind_info` JSON Schema (核心)**: (需根据实际需求详细设计，包含处理路径、LLM信息、思考链、最终行动决策、置信度、响应细节、沉默/延迟原因、V12检查结果、成本估算等，**其结构需与 `prompts.yaml` 中的要求保持一致**)
*   **测试**: 单元测试各组件 (Retriever, Assembler, Interfaces, Manager)，集成测试 L3 不同路径和 `mind_info` 输出校验。

### Layer 4: 统一风格化与安全检查

*   **目标**: 对 L3 决定要发送的内容进行最终处理，确保符合 V12 风格和安全要求。
*   **关键组件实现**:
    *   `StyleFormatter`: 应用 V12 风格规则 (全角标点、Emoji/语气词限制、Markdown格式化等)。**风格的具体规则体现在 `config/prompts.yaml` 的 `response_composer.response_prompt` 指令中，以及可能的独立配置文件。**
        *   `format(text: str, style_rules: dict) -> str`: 输入待格式化文本和风格规则，输出格式化后的文本。
    *   `ExecutionGateChecker`: 包含一系列检查器 (速率限制、系统状态、内容安全、一致性等)。
        *   `async check(mind_info: dict, global_state: dict) -> bool`: 输入 `mind_info` 和全局状态，执行所有检查，输出检查结果 (True/False)。
    *   `FinalPolisher` (L4 主控制器):
        *   `async polish(mind_info: dict) -> Optional[dict]`: 接收 `mind_info`，执行格式化（**如果使用 LLM 进行响应生成，则调用 L3 的 LLMInterfaces 并使用 `config/prompts.yaml` 中的 `response_composer.response_prompt`**）和检查，若通过则输出 `final_message_payload` 字典，否则输出 `None`。
*   **`final_message_payload` JSON Schema (核心)**: (需根据实际需求详细定义，包含目标信息和符合平台要求的最终消息格式)
*   **测试**: 单元测试格式化和各项检查逻辑，集成测试 L4 完整流程。

### Layer 5: 行为执行与反馈收集

*   **目标**: 执行最终动作，与平台交互，收集反馈数据，驱动学习。
*   **关键组件实现**:
    *   `PlatformAdapterInterface` (如 `QQAPIClient`): 封装平台 API 调用。
        *   `async send_message(payload: dict) -> dict`: 输入 `final_message_payload`，调用平台 API 发送消息，输出发送结果 (如消息 ID)。
        *   `async delete_message(message_id: str) -> bool`: (可选) 撤回消息。
        *   ...(其他平台操作)
    *   `ActionHandler`: 处理 `speak`, `remain_silent`, `delay_response`, `Send Cancelled` 等指令。
        *   `async execute(mind_info: dict, final_payload: Optional[dict]) -> None`: 根据 `mind_info` 和 `final_payload` 决定并执行最终动作（调用 `PlatformAdapterInterface` 或其他内部操作）。
    *   `FeedbackCollector`: 监控 Bot 发言后的用户反应和对话走向，结构化存储反馈数据。
        *   `monitor(sent_message_id: str, context: dict) -> None`: (内部) 开始监听与某条已发送消息相关的反馈。
        *   `async process_event(raw_event: dict) -> None`: 接收后续事件，识别和处理反馈信息，并存储。
    *   `LearningAgent / Updater` (**长期目标，难度高**): 离线/近线分析反馈数据，用于调整 L1/L2 策略、优化 L3 Prompt 或微调模型。**如果使用 LLM 进行分析，其逻辑由 `config/prompts.yaml` 中的 `learning_agent.analysis_prompt` 驱动。**
        *   `analyze_feedback(data: List[dict]) -> dict`: 输入反馈数据，输出分析结果或更新建议。
        *   `update_rules_or_models(updates: dict) -> None`: 应用更新到系统配置或模型。
*   **测试**: 单元测试 `ActionHandler`，模拟 API 测试 `PlatformAdapterInterface`，测试反馈数据存储。学习代理通常离线测试。

---

## 三、 集成与数据流

*   **核心**: 各层通过定义好的 JSON Schema 进行通信。
*   **实现**: 使用 `asyncio.Queue` 或异步调用链传递数据。
*   **关键**: 严格的数据格式校验 (推荐 Pydantic) 和异步错误处理。

---

## 四、 配置管理

*   使用中心化的 `config.yaml` 管理参数。
*   结合 `.env` 管理敏感信息。
*   使用 `ConfigManager` 加载和提供配置。
*   (可选) 使用 Pydantic 模型定义和校验配置。

---

## 五、 测试策略

*   **单元测试**: 针对关键组件和复杂逻辑。
*   **集成测试**: 测试相邻层的数据传递和交互。
*   **端到端测试**: 模拟完整流程。
*   **压力测试**: (后期) 测试高并发性能。

---

## 六、 部署

*   **Docker & Docker Compose**: 强烈推荐！
    *   `Dockerfile` 构建镜像。
    *   `docker-compose.yml` 编排服务、数据库、网络、卷。
    *   **使用 Bind Mount 将日志和数据目录映射到宿主机**。
*   **环境变量**: 管理敏感配置。
*   **资源**: 合理分配 CPU 和内存。

---

## 七、 监控与维护

*   **日志**: 依赖分级、分组件日志进行排查。
*   **指标**: (可选) Prometheus/Grafana 监控关键性能指标。
*   **告警**: 对关键错误设置告警。
*   **维护**: 定期清理、更新、调整。

---

## 八、 迭代与改进 (反馈闭环)

*   **核心**: 利用 L5 收集的数据。
*   **初期**: 人工分析，手动调整配置、Prompt、V12 原则。
*   **进阶**: 基于数据训练/微调模型，自动化优化。

---

## 九、 结论

这是一个功能强大但实现复杂的架构。建议采用**迭代式开发**策略，从核心路径开始，逐步完善。

**关键成功因素**: 清晰接口、强大 Prompt 工程、迭代开发、健壮错误处理、可观测性。

祝项目顺利！

---

## 十、 现有框架重构评估 (迁移至 5 层架构)

本部分评估将当前项目框架迁移至上述 5 层架构所需的主要重构工作。

### 1. 适配器层 (`adapters/onebot_adapter.py`)

*   **当前**: 负责平台交互、消息格式转换、事件处理。
*   **重构评估**: **中度**。
    *   修改 `_handle_event`，将原始事件推送到 L1 InputBuffer，而非直接处理。
    *   `handle_send_request` 基本满足 L5 需求，可能需微调以适应 `final_message_payload`。
    *   `MessageConverter` 可能需配合 L1 提供快速基础信息提取。

### 2. 核心 Bot 层 (`bot/linjing_bot.py`)

*   **当前**: 承担过多职责（部分过滤、上下文准备、处理器编排）。
*   **重构评估**: **显著/大部分重写**。
    *   `handle_message`, `_process_single_message`, `_execute_processor_pipeline`, `_should_process_message` 的核心逻辑将被 L1, L2, L3 的新组件取代或移除。
    *   `LinjingBot` 类将转变为顶层协调器，管理全局状态接口和层级调用流，移除具体消息处理逻辑。

### 3. 并发控制层 (`linjing_concurrent/`)

*   **当前**: `QueueManager`/`TypedRequestQueue` 按会话排队，`MessageDebouncer` 功能与 L1 缓冲重叠。
*   **重构评估**: **中度到显著**。
    *   `QueueManager`/`TypedRequestQueue` 的职责将被 L2 调度逻辑取代或大幅修改。
    *   `MessageDebouncer` 可能被 L1 的 `InputBuffer` 取代或重构。
    *   **需要新增** L3 的 LLM 并发管理器和 L4 的发送速率限制器。

### 4. 处理器层 (`processors/`)

*   **当前**: 各处理器通过 `MessageContext` 传递状态。
*   **重构评估**: **显著/核心重构**。
    *   **需要新建** L1 的 `FastSenseNLPModule`, `LightweightV12TriggerScanner`。
    *   现有 L3 级处理器 (`ReadAirProcessor`, `ThoughtGenerator`, `ResponseComposer` 等) **需要大幅重构**：
        *   调整输入接口。
        *   根据 L3 路径和资源提示调整核心逻辑。
        *   **必须改造为生成标准化的 `mind_info` JSON 输出**。
        *   `ResponseComposer` 角色转变为生成初步回复草稿。
    *   需要新建强大的 `PromptAssembler` 组件。

### 5. 支撑模块

*   `utils/logger.py`: **基本可用**，需确保新/重构组件正确使用。
*   `constants.py`: **少量修改**，补充新常量。
*   `memory/`, `storage/`: 可能需要**增强**检索能力和接口以支持 L3 Retriever。
*   `llm/`: `LLMManager` 需演进为 L3 `LLMInterfaces`，**中度重构**。
*   `config/`: 需要**显著扩展**以支持新架构的配置。
*   `message_context.py`: `MessageContext` 角色可能**弱化**，跨层通信依赖标准 JSON。

### 6. 重构总结

迁移至 5 层架构需要**非常显著的重构**，接近于在新架构上重组核心逻辑。建议采用**迭代式开发**：

1.  搭建 L1->L2(简化)->L3(简化)->L4(基础)->L5(发送) 的核心骨架并跑通。
2.  逐步细化和增强每一层的功能。

这将是一个提升系统智能性、鲁棒性和可维护性的重要步骤。

