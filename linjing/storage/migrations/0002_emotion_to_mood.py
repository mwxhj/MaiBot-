"""
数据库迁移脚本：从 user_emotions 表迁移到 user_moods 表
"""

import json
import sqlite3
from pathlib import Path

def migrate(db_path: str):
    """执行迁移"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 创建新表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_moods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            mood_data TEXT NOT NULL,
            timestamp REAL NOT NULL,
            UNIQUE(user_id, timestamp)
        )
        """)
        
        # 2. 迁移旧数据
        cursor.execute("SELECT user_id, emotion_data, timestamp FROM user_emotions")
        rows = cursor.fetchall()
        
        for user_id, emotion_data, timestamp in rows:
            try:
                # 转换旧数据格式
                old_data = json.loads(emotion_data)
                new_data = {
                    "mood_type": "平静",  # 默认值
                    "intensity": 0.5,     # 默认值
                    "timestamp": timestamp
                }
                
                # 如果有主导情绪，尝试转换
                if "dimensions" in old_data:
                    dominant = max(old_data["dimensions"].items(), key=lambda x: x[1])
                    new_data["mood_type"] = {
                        "happiness": "愉悦",
                        "excitement": "兴奋",
                        "confidence": "自信",
                        "friendliness": "友好",
                        "curiosity": "好奇",
                        "patience": "平静",
                        "trust": "平静"
                    }.get(dominant[0], "平静")
                    new_data["intensity"] = dominant[1]
                
                # 插入新表
                cursor.execute(
                    "INSERT INTO user_moods (user_id, mood_data, timestamp) VALUES (?, ?, ?)",
                    (user_id, json.dumps(new_data), timestamp)
                )
                
            except Exception as e:
                print(f"迁移用户 {user_id} 数据失败: {e}")
                continue
                
        # 3. 验证迁移
        cursor.execute("SELECT COUNT(*) FROM user_moods")
        new_count = cursor.fetchone()[0]
        print(f"成功迁移 {new_count} 条情绪记录")
        
        # 4. 删除旧表（可选）
        # cursor.execute("DROP TABLE IF EXISTS user_emotions")
        
        conn.commit()
        
    finally:
        conn.close()

if __name__ == "__main__":
    # 默认数据库路径
    db_path = str(Path(__file__).parent.parent.parent / "data" / "linjing.db")
    migrate(db_path)