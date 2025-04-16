#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import asyncio
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from datetime import datetime

from utils.logger import get_logger


class VectorDBManager:
    """向量数据库管理器，用于语义搜索和相似性查询"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化向量数据库管理器
        
        Args:
            config: 向量数据库配置字典
        """
        self.config = config
        self.logger = get_logger("VectorDBManager")
        self.is_connected = False
        
        # 确定使用哪种向量数据库实现
        self.vector_db_type = self.config.get("type", "in_memory").lower()
        
        # 默认嵌入维度
        self.embedding_dim = self.config.get("embedding_dim", 1536)  # OpenAI默认维度
        
        # 初始化适当的实现
        if self.vector_db_type == "in_memory":
            self.db = InMemoryVectorDB(self.embedding_dim)
        elif self.vector_db_type == "chroma":
            self.db = ChromaDBAdapter(self.config)
        elif self.vector_db_type == "qdrant":
            self.db = QdrantAdapter(self.config)
        elif self.vector_db_type == "pinecone":
            self.db = PineconeAdapter(self.config)
        else:
            self.logger.warning(f"未知的向量数据库类型: {self.vector_db_type}，使用内存向量数据库")
            self.db = InMemoryVectorDB(self.embedding_dim)
            
    async def connect(self) -> bool:
        """连接到向量数据库
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self.is_connected = await self.db.connect()
            if self.is_connected:
                self.logger.info(f"已成功连接到向量数据库: {self.vector_db_type}")
            else:
                self.logger.error(f"连接向量数据库失败: {self.vector_db_type}")
            return self.is_connected
        except Exception as e:
            self.logger.error(f"连接向量数据库时出错: {str(e)}")
            self.is_connected = False
            return False
    
    async def close(self) -> None:
        """关闭向量数据库连接"""
        if self.is_connected:
            await self.db.close()
            self.is_connected = False
            self.logger.info(f"向量数据库连接已关闭: {self.vector_db_type}")
    
    async def ping(self) -> bool:
        """检查向量数据库连接是否可用
        
        Returns:
            bool: 连接是否正常
        """
        if not self.is_connected:
            return False
        
        try:
            return await self.db.ping()
        except Exception as e:
            self.logger.error(f"向量数据库ping失败: {str(e)}")
            return False
    
    async def create_collection(self, collection_name: str) -> bool:
        """创建向量集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 操作是否成功
        """
        try:
            return await self.db.create_collection(collection_name)
        except Exception as e:
            self.logger.error(f"创建向量集合'{collection_name}'失败: {str(e)}")
            return False
    
    async def delete_collection(self, collection_name: str) -> bool:
        """删除向量集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 操作是否成功
        """
        try:
            return await self.db.delete_collection(collection_name)
        except Exception as e:
            self.logger.error(f"删除向量集合'{collection_name}'失败: {str(e)}")
            return False
    
    async def list_collections(self) -> List[str]:
        """列出所有向量集合
        
        Returns:
            List[str]: 集合名称列表
        """
        try:
            return await self.db.list_collections()
        except Exception as e:
            self.logger.error(f"列出向量集合失败: {str(e)}")
            return []
    
    async def add_vectors(self, 
                          collection_name: str, 
                          vectors: List[List[float]], 
                          documents: List[Dict[str, Any]], 
                          ids: Optional[List[str]] = None) -> List[str]:
        """添加向量到集合
        
        Args:
            collection_name: 集合名称
            vectors: 向量列表，每个向量是一个浮点数列表
            documents: 文档元数据列表，每个文档是一个字典
            ids: 可选的ID列表，如果不提供则自动生成
            
        Returns:
            List[str]: 添加的向量ID列表
        """
        try:
            # 验证输入
            if len(vectors) != len(documents):
                raise ValueError("向量和文档数量不匹配")
                
            if ids is not None and len(ids) != len(vectors):
                raise ValueError("ID和向量数量不匹配")
                
            # 添加时间戳
            for doc in documents:
                if "created_at" not in doc:
                    doc["created_at"] = datetime.utcnow().isoformat()
                    
            return await self.db.add_vectors(collection_name, vectors, documents, ids)
        except Exception as e:
            self.logger.error(f"向集合'{collection_name}'添加向量失败: {str(e)}")
            return []
    
    async def delete_vectors(self, collection_name: str, ids: List[str]) -> bool:
        """从集合中删除向量
        
        Args:
            collection_name: 集合名称
            ids: 要删除的向量ID列表
            
        Returns:
            bool: 操作是否成功
        """
        try:
            return await self.db.delete_vectors(collection_name, ids)
        except Exception as e:
            self.logger.error(f"从集合'{collection_name}'删除向量失败: {str(e)}")
            return False
    
    async def search_vectors(self, 
                             collection_name: str, 
                             query_vector: List[float], 
                             top_k: int = 10, 
                             filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """搜索最相似的向量
        
        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            top_k: 返回结果数量
            filter_dict: 过滤条件字典
            
        Returns:
            List[Dict[str, Any]]: 搜索结果列表，每个结果包含id、document和score字段
        """
        try:
            return await self.db.search_vectors(collection_name, query_vector, top_k, filter_dict)
        except Exception as e:
            self.logger.error(f"在集合'{collection_name}'中搜索向量失败: {str(e)}")
            return []
    
    async def get_vectors(self, collection_name: str, ids: List[str]) -> List[Dict[str, Any]]:
        """获取指定ID的向量和文档
        
        Args:
            collection_name: 集合名称
            ids: 向量ID列表
            
        Returns:
            List[Dict[str, Any]]: 向量和文档列表，每个元素包含id、vector和document字段
        """
        try:
            return await self.db.get_vectors(collection_name, ids)
        except Exception as e:
            self.logger.error(f"从集合'{collection_name}'获取向量失败: {str(e)}")
            return []
    
    async def update_vectors(self, 
                             collection_name: str, 
                             ids: List[str], 
                             vectors: Optional[List[List[float]]] = None, 
                             documents: Optional[List[Dict[str, Any]]] = None) -> bool:
        """更新向量或文档
        
        Args:
            collection_name: 集合名称
            ids: 向量ID列表
            vectors: 可选的新向量列表
            documents: 可选的新文档列表
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 确保至少提供了一个更新
            if vectors is None and documents is None:
                raise ValueError("必须提供向量或文档进行更新")
                
            # 如果提供了向量，验证数量
            if vectors is not None and len(vectors) != len(ids):
                raise ValueError("向量和ID数量不匹配")
                
            # 如果提供了文档，验证数量并添加更新时间
            if documents is not None:
                if len(documents) != len(ids):
                    raise ValueError("文档和ID数量不匹配")
                    
                for doc in documents:
                    doc["updated_at"] = datetime.utcnow().isoformat()
                    
            return await self.db.update_vectors(collection_name, ids, vectors, documents)
        except Exception as e:
            self.logger.error(f"更新集合'{collection_name}'中的向量失败: {str(e)}")
            return False
    
    async def count_vectors(self, collection_name: str, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """计算集合中的向量数量
        
        Args:
            collection_name: 集合名称
            filter_dict: 可选的过滤条件
            
        Returns:
            int: 向量数量
        """
        try:
            return await self.db.count_vectors(collection_name, filter_dict)
        except Exception as e:
            self.logger.error(f"计算集合'{collection_name}'中的向量数量失败: {str(e)}")
            return 0
    
    async def upsert_vectors(self, 
                           collection_name: str, 
                           vectors: List[List[float]], 
                           documents: List[Dict[str, Any]], 
                           ids: List[str]) -> List[str]:
        """添加或更新向量
        
        Args:
            collection_name: 集合名称
            vectors: 向量列表
            documents: 文档列表
            ids: ID列表
            
        Returns:
            List[str]: 添加或更新的向量ID列表
        """
        try:
            # 验证输入
            if len(vectors) != len(documents) or len(vectors) != len(ids):
                raise ValueError("向量、文档和ID数量不匹配")
                
            # 添加时间戳
            for doc in documents:
                if "created_at" not in doc:
                    doc["created_at"] = datetime.utcnow().isoformat()
                doc["updated_at"] = datetime.utcnow().isoformat()
                
            return await self.db.upsert_vectors(collection_name, vectors, documents, ids)
        except Exception as e:
            self.logger.error(f"向集合'{collection_name}'添加或更新向量失败: {str(e)}")
            return []


class InMemoryVectorDB:
    """基于内存的向量数据库实现，用于开发和测试"""
    
    def __init__(self, embedding_dim: int):
        """初始化内存向量数据库
        
        Args:
            embedding_dim: 嵌入向量维度
        """
        self.embedding_dim = embedding_dim
        self.collections = {}  # 集合名称 -> 集合数据的映射
        self.logger = get_logger("InMemoryVectorDB")
        
    async def connect(self) -> bool:
        """连接（内存数据库不需要实际连接）
        
        Returns:
            bool: 始终返回True
        """
        return True
    
    async def close(self) -> None:
        """关闭连接（内存数据库不需要关闭）"""
        pass
    
    async def ping(self) -> bool:
        """检查连接
        
        Returns:
            bool: 始终返回True
        """
        return True
    
    async def create_collection(self, collection_name: str) -> bool:
        """创建集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 是否成功
        """
        if collection_name not in self.collections:
            self.collections[collection_name] = {
                "ids": [],
                "vectors": [],
                "documents": []
            }
        return True
    
    async def delete_collection(self, collection_name: str) -> bool:
        """删除集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 是否成功
        """
        if collection_name in self.collections:
            del self.collections[collection_name]
            return True
        return False
    
    async def list_collections(self) -> List[str]:
        """列出所有集合
        
        Returns:
            List[str]: 集合名称列表
        """
        return list(self.collections.keys())
    
    async def add_vectors(self, 
                          collection_name: str, 
                          vectors: List[List[float]], 
                          documents: List[Dict[str, Any]], 
                          ids: Optional[List[str]] = None) -> List[str]:
        """添加向量到集合
        
        Args:
            collection_name: 集合名称
            vectors: 向量列表
            documents: 文档列表
            ids: 可选的ID列表
            
        Returns:
            List[str]: 添加的向量ID列表
        """
        # 确保集合存在
        if collection_name not in self.collections:
            await self.create_collection(collection_name)
            
        collection = self.collections[collection_name]
        
        # 如果没有提供ID，则生成ID
        if ids is None:
            # 生成从当前最大ID开始的新ID
            start_id = len(collection["ids"])
            ids = [str(i) for i in range(start_id, start_id + len(vectors))]
            
        # 添加数据
        collection["ids"].extend(ids)
        collection["vectors"].extend(vectors)
        collection["documents"].extend(documents)
        
        return ids
    
    async def delete_vectors(self, collection_name: str, ids: List[str]) -> bool:
        """从集合中删除向量
        
        Args:
            collection_name: 集合名称
            ids: 向量ID列表
            
        Returns:
            bool: 是否成功
        """
        if collection_name not in self.collections:
            return False
            
        collection = self.collections[collection_name]
        
        # 找出要保留的索引
        indices_to_keep = [i for i, id in enumerate(collection["ids"]) if id not in ids]
        
        # 重建集合，只保留需要的元素
        collection["ids"] = [collection["ids"][i] for i in indices_to_keep]
        collection["vectors"] = [collection["vectors"][i] for i in indices_to_keep]
        collection["documents"] = [collection["documents"][i] for i in indices_to_keep]
        
        return True
    
    async def search_vectors(self, 
                             collection_name: str, 
                             query_vector: List[float], 
                             top_k: int = 10, 
                             filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """搜索最相似的向量
        
        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            top_k: 返回结果数量
            filter_dict: 过滤条件
            
        Returns:
            List[Dict[str, Any]]: 搜索结果
        """
        if collection_name not in self.collections:
            return []
            
        collection = self.collections[collection_name]
        
        if not collection["vectors"]:
            return []
            
        # 转换为NumPy数组进行计算
        query_array = np.array(query_vector)
        vectors_array = np.array(collection["vectors"])
        
        # 计算余弦相似度
        norm_query = np.linalg.norm(query_array)
        norm_vectors = np.linalg.norm(vectors_array, axis=1)
        dot_product = np.dot(vectors_array, query_array)
        similarities = dot_product / (norm_vectors * norm_query)
        
        # 找出相似度最高的索引
        indices = np.argsort(-similarities)
        
        # 应用过滤条件
        if filter_dict:
            filtered_indices = []
            for i in indices:
                doc = collection["documents"][i]
                match = True
                for key, value in filter_dict.items():
                    if key not in doc or doc[key] != value:
                        match = False
                        break
                if match:
                    filtered_indices.append(i)
            indices = filtered_indices
        
        # 限制结果数量
        indices = indices[:top_k]
        
        # 构建结果
        results = []
        for i in indices:
            results.append({
                "id": collection["ids"][i],
                "document": collection["documents"][i],
                "score": float(similarities[i])
            })
            
        return results
    
    async def get_vectors(self, collection_name: str, ids: List[str]) -> List[Dict[str, Any]]:
        """获取指定ID的向量和文档
        
        Args:
            collection_name: 集合名称
            ids: 向量ID列表
            
        Returns:
            List[Dict[str, Any]]: 向量和文档列表
        """
        if collection_name not in self.collections:
            return []
            
        collection = self.collections[collection_name]
        
        results = []
        for id in ids:
            try:
                index = collection["ids"].index(id)
                results.append({
                    "id": id,
                    "vector": collection["vectors"][index],
                    "document": collection["documents"][index]
                })
            except ValueError:
                # ID不存在
                pass
                
        return results
    
    async def update_vectors(self, 
                             collection_name: str, 
                             ids: List[str], 
                             vectors: Optional[List[List[float]]] = None, 
                             documents: Optional[List[Dict[str, Any]]] = None) -> bool:
        """更新向量或文档
        
        Args:
            collection_name: 集合名称
            ids: 向量ID列表
            vectors: 可选的新向量列表
            documents: 可选的新文档列表
            
        Returns:
            bool: 是否成功
        """
        if collection_name not in self.collections:
            return False
            
        collection = self.collections[collection_name]
        
        for i, id in enumerate(ids):
            try:
                index = collection["ids"].index(id)
                
                # 更新向量
                if vectors is not None:
                    collection["vectors"][index] = vectors[i]
                    
                # 更新文档
                if documents is not None:
                    collection["documents"][index] = documents[i]
            except ValueError:
                # ID不存在
                pass
                
        return True
    
    async def count_vectors(self, collection_name: str, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """计算集合中的向量数量
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            
        Returns:
            int: 向量数量
        """
        if collection_name not in self.collections:
            return 0
            
        collection = self.collections[collection_name]
        
        if not filter_dict:
            return len(collection["ids"])
            
        # 应用过滤条件
        count = 0
        for doc in collection["documents"]:
            match = True
            for key, value in filter_dict.items():
                if key not in doc or doc[key] != value:
                    match = False
                    break
            if match:
                count += 1
                
        return count
    
    async def upsert_vectors(self, 
                             collection_name: str, 
                             vectors: List[List[float]], 
                             documents: List[Dict[str, Any]], 
                             ids: List[str]) -> List[str]:
        """添加或更新向量
        
        Args:
            collection_name: 集合名称
            vectors: 向量列表
            documents: 文档列表
            ids: ID列表
            
        Returns:
            List[str]: 添加或更新的向量ID列表
        """
        if collection_name not in self.collections:
            await self.create_collection(collection_name)
            
        collection = self.collections[collection_name]
        
        # 对每个ID，如果存在则更新，不存在则添加
        for i, id in enumerate(ids):
            if id in collection["ids"]:
                # 更新
                index = collection["ids"].index(id)
                collection["vectors"][index] = vectors[i]
                collection["documents"][index] = documents[i]
            else:
                # 添加
                collection["ids"].append(id)
                collection["vectors"].append(vectors[i])
                collection["documents"].append(documents[i])
                
        return ids


# 以下为可选的适配器实现，根据项目需要加载相应的库

class ChromaDBAdapter:
    """ChromaDB向量数据库适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化ChromaDB适配器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.client = None
        self.logger = get_logger("ChromaDBAdapter")
        self.persist_directory = self.config.get("persist_directory", "./chroma_data")
        
    async def connect(self) -> bool:
        """连接到ChromaDB
        
        Returns:
            bool: 是否成功
        """
        try:
            # 这里需要导入chromadb库
            import chromadb
            from chromadb.config import Settings
            
            # 创建客户端
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False
                )
            )
            
            return True
        except ImportError:
            self.logger.error("ChromaDB库未安装。请使用 'pip install chromadb' 安装")
            return False
        except Exception as e:
            self.logger.error(f"连接ChromaDB失败: {str(e)}")
            return False
    
    # 实现其他方法...


class QdrantAdapter:
    """Qdrant向量数据库适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化Qdrant适配器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.client = None
        self.logger = get_logger("QdrantAdapter")
        
    async def connect(self) -> bool:
        """连接到Qdrant
        
        Returns:
            bool: 是否成功
        """
        try:
            # 这里需要导入qdrant_client库
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            
            # 获取连接配置
            url = self.config.get("url")
            api_key = self.config.get("api_key")
            
            if url:
                # 远程Qdrant服务
                self.client = QdrantClient(url=url, api_key=api_key)
            else:
                # 本地Qdrant服务
                path = self.config.get("path", "./qdrant_data")
                self.client = QdrantClient(path=path)
                
            # 测试连接
            self.client.get_collections()
            
            return True
        except ImportError:
            self.logger.error("Qdrant库未安装。请使用 'pip install qdrant-client' 安装")
            return False
        except Exception as e:
            self.logger.error(f"连接Qdrant失败: {str(e)}")
            return False
    
    # 实现其他方法...


class PineconeAdapter:
    """Pinecone向量数据库适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化Pinecone适配器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.client = None
        self.logger = get_logger("PineconeAdapter")
        
    async def connect(self) -> bool:
        """连接到Pinecone
        
        Returns:
            bool: 是否成功
        """
        try:
            # 这里需要导入pinecone库
            import pinecone
            
            # 获取连接配置
            api_key = self.config.get("api_key")
            environment = self.config.get("environment")
            
            if not api_key or not environment:
                self.logger.error("Pinecone配置缺少必要参数: api_key或environment")
                return False
                
            # 初始化Pinecone
            pinecone.init(api_key=api_key, environment=environment)
            
            # 验证连接
            pinecone.whoami()
            
            return True
        except ImportError:
            self.logger.error("Pinecone库未安装。请使用 'pip install pinecone-client' 安装")
            return False
        except Exception as e:
            self.logger.error(f"连接Pinecone失败: {str(e)}")
            return False
    
    # 实现其他方法... 