#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜聊天机器人主程序入口。
"""

import sys

# 尝试显式移除旧的 config 模块缓存，以防万一
if 'linjing.config' in sys.modules:
    print("DEBUG: Removing 'linjing.config' from sys.modules") # 添加调试打印
    del sys.modules['linjing.config']
if 'linjing.config.config' in sys.modules: # 也移除可能的子模块缓存
     print("DEBUG: Removing 'linjing.config.config' from sys.modules") # 添加调试打印
     del sys.modules['linjing.config.config']

import os
# sys 已经导入过了
import signal
import asyncio
import argparse
import logging
import yaml     # 添加 yaml 导入
import dotenv   # 添加 dotenv 导入
from typing import Dict, Any, Optional

# 设置模块导入路径，确保能找到 linjing 包
# 将 MaiBot- 目录添加到 sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from linjing import ConfigManager # 直接从 linjing 包导入 ConfigManager 类
# 确定 .env 文件相对于 main.py 的路径
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
dotenv.load_dotenv(dotenv_path=dotenv_path)
logger_for_dotenv = logging.getLogger(__name__ + ".dotenv") # Use a specific logger
logger_for_dotenv.info(f"Attempting to load .env file from: {dotenv_path}")
if os.path.exists(dotenv_path):
    logger_for_dotenv.info(".env file loaded successfully.")
else:
    logger_for_dotenv.warning(".env file not found at the expected location.")


# ConfigManager class definition removed, now imported from linjing.config
# 导入其他必要的类和函数
from linjing.constants import VERSION
from linjing.bot.linjing_bot import LinjingBot
from linjing.utils.logger import get_logger # 只导入 get_logger
from loguru import logger as loguru_logger # 直接导入 loguru

# 设置日志记录器
logger = None # 将在 setup_logging 后初始化
stop_event = asyncio.Event() # 用于全局停止信号

# L1 组件
from linjing.l1_fast_sense.input_buffer import InputBuffer
from linjing.l1_fast_sense.context_aggregator import ContextAggregator
from linjing.l1_fast_sense.trigger_scanner import LightweightV12TriggerScanner
from linjing.l1_fast_sense.fast_sense_nlp import FastSenseNLPModule
from linjing.l1_fast_sense.processor import FastSenseProcessor

# L2 组件
from linjing.l2_adaptive_dispatcher.state_monitor import SimpleStateMonitor, StateMonitorInterface
from linjing.l2_adaptive_dispatcher.decision_engine import SimpleRuleBasedDecisionEngine, DecisionEngineInterface
from linjing.l2_adaptive_dispatcher.adaptive_dispatcher import AdaptiveDispatcher

# 模拟 L3/L4/L5 依赖 (稍后定义)
# from linjing.llm.llm_interface import LLMInterface # 实际组件
# from linjing.processors.prompt_assembler import PromptAssembler # 实际组件
# from linjing.adapters.base_adapter import BaseAdapter # L5 发送需要

# --- 全局变量 ---
logger = None # 将在 setup_logging 后初始化
stop_event = asyncio.Event() # 用于全局停止信号

# --- 模拟组件定义 ---
class MockLLMInterface:
    """模拟 LLM 接口，用于 L1 测试。"""
    async def invoke(self, prompt: str, model_name: str, config: Dict[str, Any]) -> str:
        logger.debug(f"MockLLMInterface invoked for model {model_name} with config: {config}")
        logger.trace(f"Mock Prompt: {prompt[:100]}...")
        # 返回一个符合 L1 NLP 期望的简单 JSON 字符串
        mock_response = {
            "basic_analysis": {
                "style": ["informal"],
                "sentiment_hint": {"primary": "neutral", "score": 0.1},
                "intent_hint": {"primary": "chat", "confidence": 0.6},
                "keywords": ["hello", "test"]
            }
        }
        import json
        return json.dumps(mock_response)

class MockPromptAssembler:
    """模拟 Prompt Assembler，用于 L1 测试。"""
    def assemble(self, prompt_key: str, context_data: Dict[str, Any]) -> Optional[str]:
        logger.debug(f"MockPromptAssembler asked for key '{prompt_key}' with data keys: {list(context_data.keys())}")
        if prompt_key == "fast_sense_processor.analysis_prompt":
            return "This is a mock prompt for fast sense analysis."
        logger.warning(f"MockPromptAssembler received unexpected key: {prompt_key}")
        return None

# --- 配置 (简化) ---
# TODO: 从文件或环境变量加载真实配置
CONFIG = {
    "logging": {
        "level": "DEBUG", # 可以调整日志级别
        "log_file_path": "logs/linjing_main.log"
    },
    "redis": {
        "redis_host": "localhost",
        "redis_port": 6379,
        "redis_db": 0,
        "redis_password": None,
        "l1_context_cache_max_len": 10,
        "l1_context_key_prefix": "l1ctx:",
        "user_activity_window_sec": 60
    },
    "l1": {
        "trigger_rules_path": "config/l1_trigger_rules.yaml",
        "nlp_config": {
            "l1_llm_model": "mock_fast_model", # 指向模拟模型
            "l1_llm_config": {"temperature": 0.1} # 模拟的 LLM 配置
        },
        "processor_config": {
            "bot_name": "林镜"
        }
    },
    "l2": {
        "state_monitor_config": {
            "initial_bot_mode": "standard"
        },
        "decision_engine_config": {}
    }
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="林镜聊天机器人")
    parser.add_argument("-c", "--config", help="YAML 配置文件路径")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式 (覆盖配置文件中的日志级别)")
    parser.add_argument("-v", "--version", action="store_true", help="显示版本信息")
    return parser.parse_args()

def handle_signals() -> None:
    def signal_handler(sig, frame):
        logger.info("收到退出信号，正在关闭...")
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.stop()
        except RuntimeError:
             logger.warning("无法获取正在运行的事件循环来停止。")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main_async(config: Dict[str, Any]) -> None:
    logger.info(f"林镜聊天机器人 v{VERSION} 正在启动...")
    bot = None
    try:
        bot = LinjingBot(config)
        logger.info("正在初始化机器人...")
        if not await bot.initialize():
            logger.error("机器人初始化失败，退出。")
            return
        logger.info("机器人初始化完成。")
        logger.info("正在启动机器人...")
        await bot.start()
        logger.info("机器人启动完成，进入主循环。")
        stop_event = asyncio.Future()
        await stop_event
    except asyncio.CancelledError:
        logger.info("主任务被取消")
    except Exception as e:
        logger.exception(f"在机器人初始化或运行过程中发生致命错误: {e}")
    finally:
        if bot and hasattr(bot, 'is_running') and bot.is_running():
             logger.info("正在停止机器人...")
             await bot.stop()
             logger.info("机器人已停止。")
        else:
             logger.info("机器人未运行或未完全初始化，无需停止。")

def main() -> None:
    args = parse_args()
    if args.version:
        print(f"林镜聊天机器人 v{VERSION}")
        sys.exit(0)

    # 获取命令行指定的配置文件路径
    config_path_arg = args.config if args.config else None

    # 创建 ConfigManager 实例，如果命令行指定了路径，则使用它
    config_manager = ConfigManager(config_path=config_path_arg)
    logger.info(f"ConfigManager instance created. Using config file: {config_manager.config_path}")
    # 显式调用 load 方法来加载配置、覆盖环境变量和设置路径
    config_manager.load()

    # 设置日志级别 (现在可以安全地从已加载的配置中获取)
    log_level_from_config = config_manager.get("system.log_level", "INFO")
    log_level = "DEBUG" if args.debug else log_level_from_config
    logger.info(f"日志级别将基于配置或命令行参数 --debug 设置。命令行参数 --debug: {args.debug}, 配置级别: {log_level_from_config}")

    # 调用 setup_logger，传入 config_manager 实例
    # log_dir 参数现在是可选的，setup_logger 会从 config_manager 获取路径
    # setup_logger(config_manager, level=log_level) # log_level 现在由配置或 --debug 决定
    # 记录实际使用的日志目录 (从 config_manager 获取)
    actual_log_dir = getattr(config_manager, 'LOG_PATH', 'Unknown') # 获取实际路径用于记录
    logger.info(f"日志级别设置为: {log_level}")
    logger.info(f"日志文件目录: {actual_log_dir}")


    handle_signals()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # 将全局配置字典传递给 main_async
        # 将 config_manager 的配置字典传递给 main_async
        loop.run_until_complete(main_async(config_manager.config))
    except KeyboardInterrupt:
        logger.info("接收到键盘中断")
    finally:
        logger.info("开始关闭事件循环...")
        tasks = asyncio.all_tasks(loop)
        if tasks:
             logger.info(f"取消 {len(tasks)} 个剩余任务...")
             for task in tasks:
                  task.cancel()
             loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
             logger.info("剩余任务已处理。")
        loop.close()
        logger.info("事件循环已关闭。")

# --- 日志记录消费者 (L3/L5 占位符) ---
async def logging_consumer(queue: asyncio.Queue, name: str):
    """简单的异步任务，消耗队列中的项目并记录日志。"""
    if not logger:
        print(f"错误：Logger 未初始化！无法启动消费者 {name}。")
        return
    logger.info(f"Logging Consumer '{name}' started, listening to queue: {queue}")
    while not stop_event.is_set(): # 检查全局停止信号
        try:
            # 使用 timeout 来允许周期性检查 stop_event
            item = await asyncio.wait_for(queue.get(), timeout=1.0)
            logger.info(f"[{name}] Received: {item}")
            queue.task_done()
        except asyncio.TimeoutError:
            # 超时是正常的，继续循环以检查 stop_event
            continue
        except asyncio.CancelledError:
            logger.info(f"Logging Consumer '{name}' task cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in Logging Consumer '{name}': {e}", exc_info=True)
            try:
                # 即使出错也尝试标记 task_done，避免队列阻塞
                queue.task_done()
            except ValueError:
                pass # 如果 get() 失败则 task_done 可能无效
            except Exception as e_td:
                logger.error(f"Error calling task_done in Logging Consumer '{name}' after exception: {e_td}")
            # 短暂休眠避免错误循环过快
            await asyncio.sleep(0.5)
    logger.info(f"Logging Consumer '{name}' stopped.")

# --- 信号处理 ---
def handle_signal(sig, frame):
    """处理 SIGINT 和 SIGTERM 信号，设置停止事件。"""
    if logger:
        logger.info(f"收到信号 {sig}, 正在请求停止...")
    else:
        print(f"收到信号 {sig}, 正在请求停止...")
    stop_event.set() # 设置全局停止事件

# --- 主函数 ---
async def main():
    """程序主入口，初始化并运行所有组件。"""
    global logger

    # 1. 设置日志 (直接使用 Loguru)
    log_config = CONFIG.get("logging", {})
    log_level = log_config.get("level", "INFO")
    log_file_path_pattern = log_config.get("log_file_path", "logs/linjing_main_{time:YYYY-MM-DD}.log")
    log_dir = os.path.dirname(log_file_path_pattern)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    loguru_logger.remove() # 移除默认处理器
    loguru_logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True
    )
    loguru_logger.add(
        log_file_path_pattern, # 使用带时间格式的文件名
        level=log_level,
        rotation="00:00",
        retention="7 days", # 简单设置保留时间
        compression="zip",
        encoding="utf-8",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} - "
            "{message}"
        )
        # enqueue=True # 可以考虑开启异步日志写入
    )
    # 设置全局 logger 变量 (虽然现在主要用 loguru_logger)
    # logger = get_logger("main") # get_logger 内部可能依赖 setup_logger，暂时注释掉
    logger = loguru_logger # 直接使用配置好的 loguru logger
    logger.info("使用 Loguru 直接配置日志完成。")

    logger.info("林镜 Bot (5 层架构重构) 启动中...")

    # 2. 创建队列
    # 注意：队列大小可以根据需要调整配置
    input_buffer_queue = InputBuffer(max_size=1000) # L0 -> L1 的队列在 InputBuffer 内部管理
    l1_output_queue = asyncio.Queue(maxsize=500)     # L1 -> L2
    l3_path_a_queue = asyncio.Queue(maxsize=100)     # L2 -> L3 Path A
    l3_path_b_queue = asyncio.Queue(maxsize=100)     # L2 -> L3 Path B
    l3_path_c_queue = asyncio.Queue(maxsize=200)     # L2 -> L3 Path C (可能量更大)
    l5_action_queue = asyncio.Queue(maxsize=100)     # L2 -> L5 Direct Action
    logger.info("所有层间队列已创建。")

    # 3. 实例化组件
    try:
        # L1 组件
        redis_config = CONFIG.get("redis", {})
        context_aggregator = ContextAggregator(config=redis_config)
        # 尝试测试 Redis 连接 (可选, 异步运行)
        # asyncio.create_task(context_aggregator._test_redis_connection())

        l1_config = CONFIG.get("l1", {})
        trigger_config = {"l1_trigger_rules_path": l1_config.get("trigger_rules_path")}
        trigger_scanner = LightweightV12TriggerScanner(config=trigger_config)

        # 使用模拟的 LLM 和 Prompt Assembler
        mock_llm = MockLLMInterface()
        mock_prompter = MockPromptAssembler()
        nlp_module = FastSenseNLPModule(llm_interface=mock_llm,
                                        prompt_assembler=mock_prompter,
                                        config=l1_config.get("nlp_config"))

        l1_processor = FastSenseProcessor(input_buffer=input_buffer_queue,
                                          l2_dispatcher_queue=l1_output_queue,
                                          nlp_module=nlp_module,
                                          trigger_scanner=trigger_scanner,
                                          context_aggregator=context_aggregator,
                                          config=l1_config.get("processor_config"))
        logger.info("L1 组件实例化完成。")

        # L2 组件
        l2_config = CONFIG.get("l2", {})
        state_monitor = SimpleStateMonitor(config=l2_config.get("state_monitor_config"))
        decision_engine = SimpleRuleBasedDecisionEngine(config=l2_config.get("decision_engine_config"))

        l2_dispatcher = AdaptiveDispatcher(l1_output_queue=l1_output_queue,
                                           l3_path_a_queue=l3_path_a_queue,
                                           l3_path_b_queue=l3_path_b_queue,
                                           l3_path_c_queue=l3_path_c_queue,
                                           l5_action_queue=l5_action_queue,
                                           state_monitor=state_monitor,
                                           decision_engine=decision_engine,
                                           config=l2_config.get("dispatcher_config")) # 可选的 L2 配置
        logger.info("L2 组件实例化完成。")

    except Exception as e:
        logger.error(f"组件实例化失败: {e}", exc_info=True)
        return # 无法继续

    # --- 模拟事件输入 (用于测试) ---
    async def simulate_input(buffer: InputBuffer):
        """向 L1 InputBuffer 模拟输入一些事件。"""
        logger.info("启动模拟输入...")
        count = 0
        while not stop_event.is_set() and count < 5: # 模拟少量事件
            count += 1
            mock_event = {
                "post_type": "message",
                "message_type": "private",
                "message_id": f"mock_msg_{count}",
                "user_id": "10001",
                "group_id": None,
                "sender": {"nickname": "TestUser", "user_id": "10001"},
                "time": asyncio.get_event_loop().time(),
                "raw_message": f"你好，林镜！这是第 {count} 条测试消息。",
                "message": [{"type": "text", "data": {"text": f"你好，林镜！这是第 {count} 条测试消息。"}}],
                "at_me": False
            }
            if count == 3: # 模拟一个 @ 消息
                mock_event["raw_message"] = "@林镜 紧急情况，请回复！"
                mock_event["message"][0]["data"]["text"] = "@林镜 紧急情况，请回复！"
                mock_event["at_me"] = True
            if count == 4: # 模拟一个长消息
                mock_event["raw_message"] = "这是一个非常非常非常长的测试消息，目的是测试 L1 的复杂度评估是否会将其标记为中等或高复杂度，因为它超过了一定的长度阈值。" * 3
                mock_event["message"][0]["data"]["text"] = mock_event["raw_message"]

            try:
                await buffer.put(mock_event)
                logger.info(f"模拟事件 {count} 已放入 InputBuffer。")
            except asyncio.QueueFull:
                logger.warning("模拟输入时 InputBuffer 已满，暂停输入。")
                await asyncio.sleep(1)
            await asyncio.sleep(1.5) # 输入间隔
        logger.info("模拟输入结束。")

    # 4. 创建和收集任务
    tasks = []
    try:
        logger.info("创建核心任务...")
        # L1 处理器任务
        tasks.append(asyncio.create_task(l1_processor.start_processing(), name="L1_FastSenseProcessor"))
        # L2 分发器任务
        tasks.append(asyncio.create_task(l2_dispatcher.start_dispatching(), name="L2_AdaptiveDispatcher"))
        # L3/L5 日志记录消费者任务
        tasks.append(asyncio.create_task(logging_consumer(l3_path_a_queue, "L3_Path_A_Consumer"), name="L3_Path_A_Consumer"))
        tasks.append(asyncio.create_task(logging_consumer(l3_path_b_queue, "L3_Path_B_Consumer"), name="L3_Path_B_Consumer"))
        tasks.append(asyncio.create_task(logging_consumer(l3_path_c_queue, "L3_Path_C_Consumer"), name="L3_Path_C_Consumer"))
        tasks.append(asyncio.create_task(logging_consumer(l5_action_queue, "L5_Action_Consumer"), name="L5_Action_Consumer"))

        # 模拟输入任务 (仅用于测试)
        tasks.append(asyncio.create_task(simulate_input(input_buffer_queue), name="SimulateInput"))

        logger.info(f"共 {len(tasks)} 个核心任务已创建，开始运行...")
        # 等待停止信号或任何任务异常退出
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # 处理完成的任务
        for task in done:
            try:
                result = task.result() # 获取结果以暴露异常
                logger.info(f"任务 '{task.get_name()}' 正常完成。结果: {result}")
            except asyncio.CancelledError:
                logger.info(f"任务 '{task.get_name()}' 被取消。")
            except Exception as e:
                logger.error(f"任务 '{task.get_name()}' 异常退出: {e}", exc_info=True)
                # 一个任务异常退出，我们也停止其他任务
                stop_event.set()

        # 如果不是因为停止信号而结束，等待停止信号
        if not stop_event.is_set():
            logger.info("等待停止信号...")
            await stop_event.wait()

    except Exception as e:
        logger.critical(f"运行主循环时发生严重错误: {e}", exc_info=True)
    finally:
        logger.info("开始停止所有剩余任务...")
        # 取消所有挂起的任务
        remaining_tasks = asyncio.all_tasks() - {asyncio.current_task()}
        if remaining_tasks:
             logger.info(f"正在取消 {len(remaining_tasks)} 个任务...")
             for task in remaining_tasks:
                 task.cancel()
             # 等待取消完成
             await asyncio.gather(*remaining_tasks, return_exceptions=True)
             logger.info("所有任务已取消。")
        else:
             logger.info("没有需要取消的任务。")

        # 可以在这里添加其他清理逻辑，例如关闭 Redis 连接池
        # if context_aggregator and context_aggregator.redis_pool:
        #     await context_aggregator.redis_pool.disconnect()
        #     logger.info("Redis 连接池已断开。")

        logger.info("林镜 Bot 程序已停止。")

# --- 程序入口点 ---
if __name__ == "__main__":
    # 设置信号处理
    signal.signal(signal.SIGINT, handle_signal) # 处理 Ctrl+C
    signal.signal(signal.SIGTERM, handle_signal) # 处理 kill 命令

    # 获取 logger，即使在异常情况下也能记录
    # logger = get_logger("main_entry") # 可能失败，因为 setup_logger 未调用
    main_logger = loguru_logger # 直接使用 loguru

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 理论上信号处理会先捕获，这里作为后备
        main_logger.info("通过 KeyboardInterrupt 强制退出。")
    except Exception as e_run:
         # 捕获 asyncio.run() 本身的错误
         main_logger.critical(f"运行 asyncio 事件循环时发生致命错误: {e_run}", exc_info=True)
         sys.exit(1) # 以错误码退出

    sys.exit(0) # 正常退出
