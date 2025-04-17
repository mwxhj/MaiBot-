#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
知识图谱模块，管理结构化的知识和实体间的关系。
"""

import logging
import json
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """
    知识图谱，管理实体和关系的结构化存储。
    
    知识图谱由实体（节点）和关系（边）组成，用于表示和查询结构化知识。
    """
    
    def __init__(self, db_manager=None, config=None):
        """
        初始化知识图谱
        
        Args:
            db_manager: 数据库管理器实例
            config: 配置字典
        """
        self.db_manager = db_manager
        self.config = config or {}
        self.initialize_done = False
        self.entity_table = self.config.get("entity_table", "kg_entities")
        self.relation_table = self.config.get("relation_table", "kg_relations")
        
        logger.info("知识图谱初始化")
    
    async def initialize(self) -> bool:
        """
        初始化知识图谱，创建必要的数据库表
        
        Returns:
            是否初始化成功
        """
        if not self.db_manager:
            logger.warning("未提供数据库管理器，知识图谱功能将不可用")
            return False
        
        try:
            # 创建实体表
            entity_table_query = f"""
            CREATE TABLE IF NOT EXISTS {self.entity_table} (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                properties TEXT,
                created_at REAL,
                updated_at REAL
            )
            """
            
            # 创建关系表
            relation_table_query = f"""
            CREATE TABLE IF NOT EXISTS {self.relation_table} (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                properties TEXT,
                confidence REAL DEFAULT 1.0,
                created_at REAL,
                updated_at REAL,
                FOREIGN KEY (source_id) REFERENCES {self.entity_table} (id),
                FOREIGN KEY (target_id) REFERENCES {self.entity_table} (id)
            )
            """
            
            # 执行创建表的查询
            await self.db_manager.execute_query(entity_table_query)
            await self.db_manager.execute_query(relation_table_query)
            
            # 创建索引
            await self.db_manager.execute_query(
                f"CREATE INDEX IF NOT EXISTS idx_{self.entity_table}_type ON {self.entity_table} (type)"
            )
            await self.db_manager.execute_query(
                f"CREATE INDEX IF NOT EXISTS idx_{self.relation_table}_source ON {self.relation_table} (source_id)"
            )
            await self.db_manager.execute_query(
                f"CREATE INDEX IF NOT EXISTS idx_{self.relation_table}_target ON {self.relation_table} (target_id)"
            )
            await self.db_manager.execute_query(
                f"CREATE INDEX IF NOT EXISTS idx_{self.relation_table}_type ON {self.relation_table} (relation_type)"
            )
            
            self.initialize_done = True
            logger.info("知识图谱初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化知识图谱时出错: {e}", exc_info=True)
            return False
    
    async def add_entity(self, name: str, entity_type: str, properties: Dict[str, Any] = None) -> Optional[str]:
        """
        添加实体到图谱
        
        Args:
            name: 实体名称
            entity_type: 实体类型
            properties: 实体属性字典
            
        Returns:
            实体ID，如果添加失败则返回None
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法添加实体")
            return None
        
        try:
            entity_id = str(uuid.uuid4())
            properties = properties or {}
            
            import time
            current_time = time.time()
            
            query = f"""
            INSERT INTO {self.entity_table} (id, name, type, properties, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            
            await self.db_manager.execute_query(
                query,
                (
                    entity_id,
                    name,
                    entity_type,
                    json.dumps(properties),
                    current_time,
                    current_time
                )
            )
            
            logger.debug(f"实体添加成功: {name} ({entity_type})")
            return entity_id
            
        except Exception as e:
            logger.error(f"添加实体时出错: {e}", exc_info=True)
            return None
    
    async def add_relation(self, source_id: str, target_id: str, relation_type: str,
                         properties: Dict[str, Any] = None, confidence: float = 1.0) -> Optional[str]:
        """
        添加实体间的关系
        
        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            relation_type: 关系类型
            properties: 关系属性字典
            confidence: 关系置信度，范围[0-1]
            
        Returns:
            关系ID，如果添加失败则返回None
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法添加关系")
            return None
        
        try:
            # 验证实体是否存在
            source_exists = await self._entity_exists(source_id)
            target_exists = await self._entity_exists(target_id)
            
            if not source_exists:
                logger.error(f"添加关系失败: 源实体不存在 {source_id}")
                return None
                
            if not target_exists:
                logger.error(f"添加关系失败: 目标实体不存在 {target_id}")
                return None
            
            relation_id = str(uuid.uuid4())
            properties = properties or {}
            
            import time
            current_time = time.time()
            
            query = f"""
            INSERT INTO {self.relation_table} 
            (id, source_id, target_id, relation_type, properties, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            await self.db_manager.execute_query(
                query,
                (
                    relation_id,
                    source_id,
                    target_id,
                    relation_type,
                    json.dumps(properties),
                    confidence,
                    current_time,
                    current_time
                )
            )
            
            logger.debug(f"关系添加成功: {source_id} --[{relation_type}]--> {target_id}")
            return relation_id
            
        except Exception as e:
            logger.error(f"添加关系时出错: {e}", exc_info=True)
            return None
    
    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        获取实体信息
        
        Args:
            entity_id: 实体ID
            
        Returns:
            实体信息字典，如果不存在则返回None
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法获取实体")
            return None
        
        try:
            query = f"SELECT * FROM {self.entity_table} WHERE id = ?"
            results = await self.db_manager.execute_query(query, (entity_id,))
            
            if not results:
                return None
            
            entity_data = results[0]
            
            # 解析属性JSON
            if "properties" in entity_data and entity_data["properties"]:
                try:
                    entity_data["properties"] = json.loads(entity_data["properties"])
                except Exception:
                    entity_data["properties"] = {}
            else:
                entity_data["properties"] = {}
            
            return entity_data
            
        except Exception as e:
            logger.error(f"获取实体时出错: {e}", exc_info=True)
            return None
    
    async def get_relation(self, relation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取关系信息
        
        Args:
            relation_id: 关系ID
            
        Returns:
            关系信息字典，如果不存在则返回None
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法获取关系")
            return None
        
        try:
            query = f"SELECT * FROM {self.relation_table} WHERE id = ?"
            results = await self.db_manager.execute_query(query, (relation_id,))
            
            if not results:
                return None
            
            relation_data = results[0]
            
            # 解析属性JSON
            if "properties" in relation_data and relation_data["properties"]:
                try:
                    relation_data["properties"] = json.loads(relation_data["properties"])
                except Exception:
                    relation_data["properties"] = {}
            else:
                relation_data["properties"] = {}
            
            return relation_data
            
        except Exception as e:
            logger.error(f"获取关系时出错: {e}", exc_info=True)
            return None
    
    async def find_entities(self, entity_type: Optional[str] = None, name_like: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """
        查找符合条件的实体
        
        Args:
            entity_type: 实体类型过滤
            name_like: 实体名称模糊匹配
            limit: 最大返回数量
            
        Returns:
            实体信息列表
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法查找实体")
            return []
        
        try:
            conditions = []
            params = []
            
            if entity_type:
                conditions.append("type = ?")
                params.append(entity_type)
            
            if name_like:
                conditions.append("name LIKE ?")
                params.append(f"%{name_like}%")
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"SELECT * FROM {self.entity_table} WHERE {where_clause} LIMIT ?"
            params.append(limit)
            
            results = await self.db_manager.execute_query(query, tuple(params))
            
            # 处理结果
            entities = []
            for entity_data in results:
                # 解析属性JSON
                if "properties" in entity_data and entity_data["properties"]:
                    try:
                        entity_data["properties"] = json.loads(entity_data["properties"])
                    except Exception:
                        entity_data["properties"] = {}
                else:
                    entity_data["properties"] = {}
                
                entities.append(entity_data)
            
            return entities
            
        except Exception as e:
            logger.error(f"查找实体时出错: {e}", exc_info=True)
            return []
    
    async def find_relations(self, source_id: Optional[str] = None, target_id: Optional[str] = None,
                           relation_type: Optional[str] = None, min_confidence: float = 0.0,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        查找符合条件的关系
        
        Args:
            source_id: 源实体ID过滤
            target_id: 目标实体ID过滤
            relation_type: 关系类型过滤
            min_confidence: 最小置信度
            limit: 最大返回数量
            
        Returns:
            关系信息列表
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法查找关系")
            return []
        
        try:
            conditions = ["confidence >= ?"]
            params = [min_confidence]
            
            if source_id:
                conditions.append("source_id = ?")
                params.append(source_id)
            
            if target_id:
                conditions.append("target_id = ?")
                params.append(target_id)
            
            if relation_type:
                conditions.append("relation_type = ?")
                params.append(relation_type)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"SELECT * FROM {self.relation_table} WHERE {where_clause} ORDER BY confidence DESC LIMIT ?"
            params.append(limit)
            
            results = await self.db_manager.execute_query(query, tuple(params))
            
            # 处理结果
            relations = []
            for relation_data in results:
                # 解析属性JSON
                if "properties" in relation_data and relation_data["properties"]:
                    try:
                        relation_data["properties"] = json.loads(relation_data["properties"])
                    except Exception:
                        relation_data["properties"] = {}
                else:
                    relation_data["properties"] = {}
                
                relations.append(relation_data)
            
            return relations
            
        except Exception as e:
            logger.error(f"查找关系时出错: {e}", exc_info=True)
            return []
    
    async def get_entity_relations(self, entity_id: str, direction: str = "all",
                                 relation_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        获取实体的关系
        
        Args:
            entity_id: 实体ID
            direction: 关系方向，"outgoing"表示出关系，"incoming"表示入关系，"all"表示所有
            relation_types: 关系类型过滤列表
            
        Returns:
            关系信息列表
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法获取实体关系")
            return []
        
        try:
            conditions = []
            params = []
            
            if direction == "outgoing":
                conditions.append("source_id = ?")
                params.append(entity_id)
            elif direction == "incoming":
                conditions.append("target_id = ?")
                params.append(entity_id)
            else:  # "all"
                conditions.append("(source_id = ? OR target_id = ?)")
                params.append(entity_id)
                params.append(entity_id)
            
            if relation_types:
                placeholders = ", ".join(["?"] * len(relation_types))
                conditions.append(f"relation_type IN ({placeholders})")
                params.extend(relation_types)
            
            where_clause = " AND ".join(conditions)
            
            query = f"SELECT * FROM {self.relation_table} WHERE {where_clause}"
            
            results = await self.db_manager.execute_query(query, tuple(params))
            
            # 处理结果
            relations = []
            for relation_data in results:
                # 解析属性JSON
                if "properties" in relation_data and relation_data["properties"]:
                    try:
                        relation_data["properties"] = json.loads(relation_data["properties"])
                    except Exception:
                        relation_data["properties"] = {}
                else:
                    relation_data["properties"] = {}
                
                relations.append(relation_data)
            
            return relations
            
        except Exception as e:
            logger.error(f"获取实体关系时出错: {e}", exc_info=True)
            return []
    
    async def update_entity(self, entity_id: str, name: Optional[str] = None,
                          entity_type: Optional[str] = None,
                          properties: Optional[Dict[str, Any]] = None) -> bool:
        """
        更新实体信息
        
        Args:
            entity_id: 实体ID
            name: 新的实体名称，为None则不更新
            entity_type: 新的实体类型，为None则不更新
            properties: 新的实体属性，为None则不更新
            
        Returns:
            是否更新成功
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法更新实体")
            return False
        
        try:
            # 获取当前实体信息
            current = await self.get_entity(entity_id)
            if not current:
                logger.error(f"更新实体失败: 实体不存在 {entity_id}")
                return False
            
            # 准备更新数据
            import time
            update_data = {
                "updated_at": time.time()
            }
            
            if name is not None:
                update_data["name"] = name
            
            if entity_type is not None:
                update_data["type"] = entity_type
            
            if properties is not None:
                # 如果properties是更新而不是替换，则合并当前属性
                if isinstance(properties, dict) and "properties" in current:
                    current_properties = current["properties"] if isinstance(current["properties"], dict) else {}
                    merged_properties = {**current_properties, **properties}
                    update_data["properties"] = json.dumps(merged_properties)
                else:
                    update_data["properties"] = json.dumps(properties)
            
            # 如果没有任何字段需要更新，则直接返回成功
            if len(update_data) <= 1:  # 只有updated_at
                return True
            
            # 构建更新查询
            set_clause = ", ".join([f"{key} = ?" for key in update_data.keys()])
            params = list(update_data.values())
            params.append(entity_id)
            
            query = f"UPDATE {self.entity_table} SET {set_clause} WHERE id = ?"
            
            await self.db_manager.execute_query(query, tuple(params))
            
            logger.debug(f"实体更新成功: {entity_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新实体时出错: {e}", exc_info=True)
            return False
    
    async def update_relation(self, relation_id: str, relation_type: Optional[str] = None,
                            properties: Optional[Dict[str, Any]] = None,
                            confidence: Optional[float] = None) -> bool:
        """
        更新关系信息
        
        Args:
            relation_id: 关系ID
            relation_type: 新的关系类型，为None则不更新
            properties: 新的关系属性，为None则不更新
            confidence: 新的置信度，为None则不更新
            
        Returns:
            是否更新成功
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法更新关系")
            return False
        
        try:
            # 获取当前关系信息
            current = await self.get_relation(relation_id)
            if not current:
                logger.error(f"更新关系失败: 关系不存在 {relation_id}")
                return False
            
            # 准备更新数据
            import time
            update_data = {
                "updated_at": time.time()
            }
            
            if relation_type is not None:
                update_data["relation_type"] = relation_type
            
            if confidence is not None:
                update_data["confidence"] = min(1.0, max(0.0, confidence))
            
            if properties is not None:
                # 如果properties是更新而不是替换，则合并当前属性
                if isinstance(properties, dict) and "properties" in current:
                    current_properties = current["properties"] if isinstance(current["properties"], dict) else {}
                    merged_properties = {**current_properties, **properties}
                    update_data["properties"] = json.dumps(merged_properties)
                else:
                    update_data["properties"] = json.dumps(properties)
            
            # 如果没有任何字段需要更新，则直接返回成功
            if len(update_data) <= 1:  # 只有updated_at
                return True
            
            # 构建更新查询
            set_clause = ", ".join([f"{key} = ?" for key in update_data.keys()])
            params = list(update_data.values())
            params.append(relation_id)
            
            query = f"UPDATE {self.relation_table} SET {set_clause} WHERE id = ?"
            
            await self.db_manager.execute_query(query, tuple(params))
            
            logger.debug(f"关系更新成功: {relation_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新关系时出错: {e}", exc_info=True)
            return False
    
    async def delete_entity(self, entity_id: str, cascade: bool = True) -> bool:
        """
        删除实体，可选级联删除相关关系
        
        Args:
            entity_id: 实体ID
            cascade: 是否级联删除关联的关系
            
        Returns:
            是否删除成功
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法删除实体")
            return False
        
        try:
            # 如果需要级联删除相关关系
            if cascade:
                # 删除所有与该实体相关的关系
                query = f"DELETE FROM {self.relation_table} WHERE source_id = ? OR target_id = ?"
                await self.db_manager.execute_query(query, (entity_id, entity_id))
            
            # 删除实体
            query = f"DELETE FROM {self.entity_table} WHERE id = ?"
            await self.db_manager.execute_query(query, (entity_id,))
            
            logger.debug(f"实体删除成功: {entity_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除实体时出错: {e}", exc_info=True)
            return False
    
    async def delete_relation(self, relation_id: str) -> bool:
        """
        删除关系
        
        Args:
            relation_id: 关系ID
            
        Returns:
            是否删除成功
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法删除关系")
            return False
        
        try:
            # 删除关系
            query = f"DELETE FROM {self.relation_table} WHERE id = ?"
            await self.db_manager.execute_query(query, (relation_id,))
            
            logger.debug(f"关系删除成功: {relation_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除关系时出错: {e}", exc_info=True)
            return False
    
    async def find_path(self, source_id: str, target_id: str, max_depth: int = 3) -> List[List[Dict[str, Any]]]:
        """
        查找两个实体之间的路径
        
        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            max_depth: 最大路径深度
            
        Returns:
            路径列表，每个路径由关系字典组成
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法查找路径")
            return []
        
        # 避免过深的搜索
        max_depth = min(max_depth, 5)
        
        # BFS查找路径
        paths = []
        visited = set()
        queue = [[(source_id, None)]]  # (entity_id, relation_data)
        
        while queue and len(paths) < 10:  # 最多返回10条路径
            path = queue.pop(0)
            current_entity, _ = path[-1]
            
            # 如果达到目标
            if current_entity == target_id:
                # 过滤掉起点实体，只保留关系和中间实体
                processed_path = []
                for i in range(1, len(path)):
                    entity_id, relation = path[i]
                    if relation:
                        processed_path.append(relation)
                paths.append(processed_path)
                continue
            
            # 如果路径已达最大深度
            if len(path) > max_depth:
                continue
            
            # 如果已访问过该实体
            if current_entity in visited:
                continue
            
            visited.add(current_entity)
            
            # 获取所有出关系
            relations = await self.get_entity_relations(current_entity, direction="outgoing")
            
            for relation in relations:
                next_entity = relation.get("target_id")
                
                if next_entity and next_entity not in visited:
                    new_path = path.copy()
                    new_path.append((next_entity, relation))
                    queue.append(new_path)
        
        return paths
    
    async def clear(self) -> bool:
        """
        清空知识图谱
        
        Returns:
            是否清空成功
        """
        if not self.db_manager or not self.initialize_done:
            logger.warning("知识图谱未初始化，无法清空")
            return False
        
        try:
            # 清空关系表
            await self.db_manager.execute_query(f"DELETE FROM {self.relation_table}")
            
            # 清空实体表
            await self.db_manager.execute_query(f"DELETE FROM {self.entity_table}")
            
            logger.info("知识图谱已清空")
            return True
            
        except Exception as e:
            logger.error(f"清空知识图谱时出错: {e}", exc_info=True)
            return False
    
    async def _entity_exists(self, entity_id: str) -> bool:
        """
        检查实体是否存在
        
        Args:
            entity_id: 实体ID
            
        Returns:
            实体是否存在
        """
        query = f"SELECT 1 FROM {self.entity_table} WHERE id = ?"
        results = await self.db_manager.execute_query(query, (entity_id,))
        return bool(results) 