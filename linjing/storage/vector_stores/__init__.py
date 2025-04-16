#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 向量存储接口
"""

from .base_vector_store import BaseVectorStore
from .local_vector_store import LocalVectorStore

__all__ = ['BaseVectorStore', 'LocalVectorStore'] 