#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - RelationshipModels测试
"""

import unittest
import json
import time
from linjing.models.relationship_models import Impression, Interaction, Relationship


class TestImpression(unittest.TestCase):
    """Impression类测试"""
    
    def setUp(self):
        """测试初始化"""
        self.initial_familiarity = 0.3
        self.initial_trust = 0.4
        self.initial_likability = 0.5
        self.initial_respect = 0.6
        self.impression = Impression(
            familiarity=self.initial_familiarity,
            trust=self.initial_trust,
            likability=self.initial_likability,
            respect=self.initial_respect,
            tags=["友好", "乐于助人"],
            notes=["第一次交流很顺利", "对技术很感兴趣"]
        )
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.impression.familiarity, self.initial_familiarity)
        self.assertEqual(self.impression.trust, self.initial_trust)
        self.assertEqual(self.impression.likability, self.initial_likability)
        self.assertEqual(self.impression.respect, self.initial_respect)
        self.assertEqual(len(self.impression.tags), 2)
        self.assertIn("友好", self.impression.tags)
        self.assertEqual(len(self.impression.notes), 2)
        self.assertIn("第一次交流很顺利", self.impression.notes)
    
    def test_update_fields(self):
        """测试更新字段"""
        # 更新熟悉度
        self.impression.update_familiarity(0.1)
        self.assertEqual(self.impression.familiarity, 0.4)  # 0.3 + 0.1
        
        # 更新信任度
        self.impression.update_trust(0.2)
        self.assertEqual(self.impression.trust, 0.6)  # 0.4 + 0.2
        
        # 更新喜爱度
        self.impression.update_likability(-0.1)
        self.assertEqual(self.impression.likability, 0.4)  # 0.5 - 0.1
        
        # 更新尊重度
        self.impression.update_respect(-0.2)
        self.assertEqual(self.impression.respect, 0.4)  # 0.6 - 0.2
        
        # 测试边界值
        self.impression.update_familiarity(0.7)
        self.assertEqual(self.impression.familiarity, 1.0)  # 不能超过1.0
        
        self.impression.update_trust(-0.7)
        self.assertEqual(self.impression.trust, 0.0)  # 不能低于0.0
    
    def test_add_tag(self):
        """测试添加标签"""
        # 添加新标签
        self.impression.add_tag("幽默")
        self.assertIn("幽默", self.impression.tags)
        self.assertEqual(len(self.impression.tags), 3)
        
        # 添加已存在的标签
        self.impression.add_tag("友好")
        self.assertEqual(len(self.impression.tags), 3)  # 不应该重复添加
    
    def test_remove_tag(self):
        """测试移除标签"""
        # 移除存在的标签
        self.impression.remove_tag("友好")
        self.assertNotIn("友好", self.impression.tags)
        self.assertEqual(len(self.impression.tags), 1)
        
        # 移除不存在的标签
        self.impression.remove_tag("不存在的标签")
        self.assertEqual(len(self.impression.tags), 1)  # 不应该有变化
    
    def test_add_note(self):
        """测试添加笔记"""
        # 添加新笔记
        self.impression.add_note("擅长编程")
        self.assertIn("擅长编程", self.impression.notes)
        self.assertEqual(len(self.impression.notes), 3)
    
    def test_to_dict(self):
        """测试转换为字典"""
        impression_dict = self.impression.to_dict()
        self.assertEqual(impression_dict["familiarity"], self.initial_familiarity)
        self.assertEqual(impression_dict["trust"], self.initial_trust)
        self.assertEqual(impression_dict["likability"], self.initial_likability)
        self.assertEqual(impression_dict["respect"], self.initial_respect)
        self.assertEqual(len(impression_dict["tags"]), 2)
        self.assertEqual(len(impression_dict["notes"]), 2)
    
    def test_from_dict(self):
        """测试从字典创建"""
        impression_dict = {
            "familiarity": 0.7,
            "trust": 0.8,
            "likability": 0.9,
            "respect": 0.85,
            "tags": ["负责", "认真"],
            "notes": ["工作很专注"]
        }
        
        new_impression = Impression.from_dict(impression_dict)
        self.assertEqual(new_impression.familiarity, 0.7)
        self.assertEqual(new_impression.trust, 0.8)
        self.assertEqual(new_impression.likability, 0.9)
        self.assertEqual(new_impression.respect, 0.85)
        self.assertEqual(len(new_impression.tags), 2)
        self.assertIn("负责", new_impression.tags)
        self.assertEqual(len(new_impression.notes), 1)
        self.assertIn("工作很专注", new_impression.notes)


class TestInteraction(unittest.TestCase):
    """Interaction类测试"""
    
    def setUp(self):
        """测试初始化"""
        self.timestamp = time.time()
        self.interaction = Interaction(
            timestamp=self.timestamp,
            interaction_type="message",
            sentiment="positive",
            content="你好，很高兴认识你！",
            metadata={"channel": "group", "group_id": "12345"}
        )
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.interaction.timestamp, self.timestamp)
        self.assertEqual(self.interaction.interaction_type, "message")
        self.assertEqual(self.interaction.sentiment, "positive")
        self.assertEqual(self.interaction.content, "你好，很高兴认识你！")
        self.assertEqual(self.interaction.metadata["channel"], "group")
        self.assertEqual(self.interaction.metadata["group_id"], "12345")
    
    def test_to_dict(self):
        """测试转换为字典"""
        interaction_dict = self.interaction.to_dict()
        self.assertEqual(interaction_dict["timestamp"], self.timestamp)
        self.assertEqual(interaction_dict["interaction_type"], "message")
        self.assertEqual(interaction_dict["sentiment"], "positive")
        self.assertEqual(interaction_dict["content"], "你好，很高兴认识你！")
        self.assertEqual(interaction_dict["metadata"]["channel"], "group")
    
    def test_from_dict(self):
        """测试从字典创建"""
        interaction_dict = {
            "timestamp": self.timestamp + 100,
            "interaction_type": "command",
            "sentiment": "neutral",
            "content": "/help",
            "metadata": {"channel": "private"}
        }
        
        new_interaction = Interaction.from_dict(interaction_dict)
        self.assertEqual(new_interaction.timestamp, self.timestamp + 100)
        self.assertEqual(new_interaction.interaction_type, "command")
        self.assertEqual(new_interaction.sentiment, "neutral")
        self.assertEqual(new_interaction.content, "/help")
        self.assertEqual(new_interaction.metadata["channel"], "private")


class TestRelationship(unittest.TestCase):
    """Relationship类测试"""
    
    def setUp(self):
        """测试初始化"""
        self.source_id = "bot_id"
        self.target_id = "user_id"
        self.relationship_type = "user"
        self.created_at = time.time() - 1000
        
        # 创建测试印象
        self.impression = Impression(
            familiarity=0.3,
            trust=0.4,
            likability=0.5,
            respect=0.6,
            tags=["友好", "乐于助人"],
            notes=["第一次交流很顺利"]
        )
        
        # 创建测试交互
        self.interaction1 = Interaction(
            timestamp=time.time() - 900,
            interaction_type="message",
            sentiment="positive",
            content="你好，很高兴认识你！",
            metadata={"channel": "group", "group_id": "12345"}
        )
        
        self.interaction2 = Interaction(
            timestamp=time.time() - 800,
            interaction_type="message",
            sentiment="neutral",
            content="今天天气怎么样？",
            metadata={"channel": "group", "group_id": "12345"}
        )
        
        # 创建测试关系
        self.relationship = Relationship(
            source_id=self.source_id,
            target_id=self.target_id,
            relationship_type=self.relationship_type,
            created_at=self.created_at,
            source_impression=self.impression,
            interactions=[self.interaction1]
        )
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.relationship.source_id, self.source_id)
        self.assertEqual(self.relationship.target_id, self.target_id)
        self.assertEqual(self.relationship.relationship_type, self.relationship_type)
        self.assertEqual(self.relationship.created_at, self.created_at)
        self.assertEqual(self.relationship.updated_at > 0, True)
        self.assertEqual(self.relationship.source_impression.familiarity, 0.3)
        self.assertEqual(len(self.relationship.interactions), 1)
        self.assertEqual(self.relationship.interactions[0].content, "你好，很高兴认识你！")
    
    def test_add_interaction(self):
        """测试添加交互"""
        # 添加新交互
        self.relationship.add_interaction(self.interaction2)
        
        # 验证结果
        self.assertEqual(len(self.relationship.interactions), 2)
        self.assertEqual(self.relationship.interactions[1].content, "今天天气怎么样？")
        self.assertEqual(self.relationship.updated_at > self.created_at, True)
    
    def test_calculate_strength(self):
        """测试计算关系强度"""
        # 初始状态
        strength = self.relationship.calculate_strength()
        expected_strength = (0.3 + 0.4 + 0.5 + 0.6) / 4  # 平均印象值
        self.assertAlmostEqual(strength, expected_strength, places=2)
        
        # 更新印象后再计算
        self.relationship.source_impression.update_familiarity(0.2)
        self.relationship.source_impression.update_trust(0.1)
        
        updated_strength = self.relationship.calculate_strength()
        updated_expected = (0.5 + 0.5 + 0.5 + 0.6) / 4  # 更新后的平均印象值
        self.assertAlmostEqual(updated_strength, updated_expected, places=2)
    
    def test_limit_interactions(self):
        """测试限制交互数量"""
        # 添加10个交互
        for i in range(10):
            interaction = Interaction(
                timestamp=time.time() - 700 + i*10,
                interaction_type="message",
                sentiment="neutral",
                content=f"测试消息 {i}",
                metadata={}
            )
            self.relationship.add_interaction(interaction)
        
        # 现在应该有11个交互 (最初的1个 + 新增的10个)
        self.assertEqual(len(self.relationship.interactions), 11)
        
        # 限制为5个
        self.relationship.limit_interactions(5)
        
        # 验证结果
        self.assertEqual(len(self.relationship.interactions), 5)
        # 应该保留最新的5个
        self.assertEqual(self.relationship.interactions[0].content, "测试消息 5")
        self.assertEqual(self.relationship.interactions[4].content, "测试消息 9")
    
    def test_get_recent_interactions(self):
        """测试获取最近交互"""
        # 添加5个交互
        for i in range(5):
            interaction = Interaction(
                timestamp=time.time() - 700 + i*10,
                interaction_type="message",
                sentiment="neutral",
                content=f"测试消息 {i}",
                metadata={}
            )
            self.relationship.add_interaction(interaction)
        
        # 获取最近3个交互
        recent = self.relationship.get_recent_interactions(3)
        
        # 验证结果
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0].content, "测试消息 2")
        self.assertEqual(recent[2].content, "测试消息 4")
    
    def test_get_interaction_count(self):
        """测试获取交互计数"""
        # 添加不同类型的交互
        interactions = [
            Interaction(timestamp=time.time(), interaction_type="message", sentiment="positive", content="消息1", metadata={}),
            Interaction(timestamp=time.time(), interaction_type="message", sentiment="negative", content="消息2", metadata={}),
            Interaction(timestamp=time.time(), interaction_type="command", sentiment="neutral", content="/help", metadata={}),
            Interaction(timestamp=time.time(), interaction_type="message", sentiment="positive", content="消息3", metadata={})
        ]
        
        for interaction in interactions:
            self.relationship.add_interaction(interaction)
        
        # 获取所有交互计数
        total_count = self.relationship.get_interaction_count()
        self.assertEqual(total_count, 5)  # 最初的1个 + 新增的4个
        
        # 获取特定类型交互计数
        message_count = self.relationship.get_interaction_count("message")
        self.assertEqual(message_count, 4)  # 最初的1个 + 新增的3个message类型
        
        command_count = self.relationship.get_interaction_count("command")
        self.assertEqual(command_count, 1)
        
        # 获取特定情感交互计数
        positive_count = self.relationship.get_interaction_count(sentiment="positive")
        self.assertEqual(positive_count, 3)  # 最初的1个 + 新增的2个positive情感
    
    def test_to_dict(self):
        """测试转换为字典"""
        relationship_dict = self.relationship.to_dict()
        self.assertEqual(relationship_dict["source_id"], self.source_id)
        self.assertEqual(relationship_dict["target_id"], self.target_id)
        self.assertEqual(relationship_dict["relationship_type"], self.relationship_type)
        self.assertEqual(relationship_dict["created_at"], self.created_at)
        self.assertIn("updated_at", relationship_dict)
        self.assertIn("source_impression", relationship_dict)
        self.assertEqual(len(relationship_dict["interactions"]), 1)
        self.assertEqual(relationship_dict["interactions"][0]["content"], "你好，很高兴认识你！")
    
    def test_from_dict(self):
        """测试从字典创建"""
        relationship_dict = {
            "source_id": "new_bot",
            "target_id": "new_user",
            "relationship_type": "admin",
            "created_at": time.time() - 2000,
            "updated_at": time.time() - 1000,
            "source_impression": {
                "familiarity": 0.8,
                "trust": 0.9,
                "likability": 0.7,
                "respect": 0.6,
                "tags": ["专业"],
                "notes": ["表现出色"]
            },
            "interactions": [
                {
                    "timestamp": time.time() - 1500,
                    "interaction_type": "command",
                    "sentiment": "neutral",
                    "content": "/status",
                    "metadata": {"channel": "private"}
                }
            ],
            "metadata": {"custom_field": "value"}
        }
        
        new_relationship = Relationship.from_dict(relationship_dict)
        self.assertEqual(new_relationship.source_id, "new_bot")
        self.assertEqual(new_relationship.target_id, "new_user")
        self.assertEqual(new_relationship.relationship_type, "admin")
        self.assertEqual(new_relationship.source_impression.familiarity, 0.8)
        self.assertEqual(len(new_relationship.interactions), 1)
        self.assertEqual(new_relationship.interactions[0].content, "/status")
        self.assertEqual(new_relationship.metadata["custom_field"], "value")
    
    def test_generate_description(self):
        """测试生成关系描述"""
        # 基本描述
        description = self.relationship.generate_description()
        self.assertIsInstance(description, str)
        self.assertGreater(len(description), 0)
        
        # 详细描述
        detailed_description = self.relationship.generate_description(detailed=True)
        self.assertIsInstance(detailed_description, str)
        self.assertGreater(len(detailed_description), len(description))  # 详细描述应该更长
        

if __name__ == "__main__":
    unittest.main() 