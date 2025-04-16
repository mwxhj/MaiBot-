#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 导入修复脚本
用于修复项目中的导入问题
"""

import os
import re
import sys

def fix_import_in_file(file_path):
    """修复文件中的导入问题"""
    print(f"检查文件: {file_path}")
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换绝对导入为相对导入
    modified = False
    
    # 替换 from linjing.xxx.yyy import zzz 为 from ..xxx.yyy import zzz
    pattern = r'from linjing\.(\w+)\.(\w+) import (.+)'
    if "linjing/" in file_path and re.search(pattern, content):
        new_content = re.sub(pattern, r'from ..\1.\2 import \3', content)
        modified = new_content != content
        content = new_content
    
    # 替换 from linjing.xxx import yyy 为 from ..xxx import yyy
    pattern = r'from linjing\.(\w+) import (.+)'
    if "linjing/" in file_path and re.search(pattern, content):
        new_content = re.sub(pattern, r'from ..\1 import \2', content)
        modified = modified or new_content != content
        content = new_content
    
    # 替换 import linjing.xxx 为 from .. import xxx
    pattern = r'import linjing\.(\w+)'
    if "linjing/" in file_path and re.search(pattern, content):
        new_content = re.sub(pattern, r'from .. import \1', content)
        modified = modified or new_content != content
        content = new_content
    
    # 修复 chat_models 导入
    if "chat_models" in content:
        new_content = content.replace("chat_models", "message_models")
        modified = modified or new_content != content
        content = new_content
    
    # 修复单例装饰器导入
    if "@singleton" in content and "singleton" not in content.lower().split("import")[0]:
        if "from ..utils.singleton import singleton" not in content:
            import_section_end = content.find("\n\n", content.find("import"))
            if import_section_end > 0:
                new_content = content[:import_section_end] + "\nfrom ..utils.singleton import singleton" + content[import_section_end:]
                modified = modified or new_content != content
                content = new_content
    
    # 修复日志导入
    if "logging.getLogger" in content and "from ..utils.logger import get_logger" not in content:
        # 替换 logger = logging.getLogger(__name__) 为 logger = get_logger('xxx')
        pattern = r'logger\s*=\s*logging\.getLogger\(__name__\)'
        module_path = file_path.replace("\\", "/").split("linjing/")[1].replace(".py", "").replace("/", ".")
        if re.search(pattern, content):
            new_content = re.sub(pattern, f"logger = get_logger('linjing.{module_path}')", content)
            modified = modified or new_content != content
            content = new_content

            # 添加导入
            import_section_end = content.find("\n\n", content.find("import"))
            if import_section_end > 0:
                new_content = content[:import_section_end] + "\nfrom ..utils.logger import get_logger" + content[import_section_end:]
                modified = modified or new_content != content
                content = new_content
    
    # 修复错误的相对导入（处理 from ..models.chat_models 这样的情况）
    if "from ..models.chat_models" in content:
        new_content = content.replace("from ..models.chat_models", "from ..models.message_models")
        modified = modified or new_content != content
        content = new_content
    
    # 检查重复导入
    import_lines = [line.strip() for line in content.split("\n") if line.strip().startswith(("import ", "from "))]
    unique_imports = set()
    duplicate_imports = []
    
    for line in import_lines:
        if line in unique_imports:
            duplicate_imports.append(line)
        else:
            unique_imports.add(line)
    
    if duplicate_imports:
        for dup in duplicate_imports:
            pattern = f"(?m)^{re.escape(dup)}$"
            # 保留第一个，删除其他重复的
            matches = list(re.finditer(pattern, content))
            if len(matches) > 1:
                for m in matches[1:]:
                    start, end = m.span()
                    content = content[:start] + content[end+1:] if end < len(content) else content[:start]
                    modified = True
    
    # 保存修改
    if modified:
        print(f"修复文件: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def fix_imports_in_directory(root_dir):
    """修复目录中所有Python文件的导入问题"""
    fixed_count = 0
    
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if fix_import_in_file(file_path):
                    fixed_count += 1
    
    return fixed_count

def create_utils_singleton(root_dir):
    """创建utils/singleton.py文件（如果不存在）"""
    utils_dir = os.path.join(root_dir, "utils")
    singleton_path = os.path.join(utils_dir, "singleton.py")
    
    if not os.path.exists(singleton_path):
        print(f"创建文件: {singleton_path}")
        
        singleton_content = """#!/usr/bin/env python
# -*- coding: utf-8 -*-

\"\"\"
林镜(LingJing) - 单例装饰器工具
\"\"\"

def singleton(cls):
    \"\"\"
    单例装饰器，确保类只有一个实例
    
    Args:
        cls: 要装饰的类
        
    Returns:
        装饰后的类，具有单例特性
    \"\"\"
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance
"""
        os.makedirs(utils_dir, exist_ok=True)
        with open(singleton_path, 'w', encoding='utf-8') as f:
            f.write(singleton_content)
        return True
    
    return False

def main():
    """主函数"""
    print("林镜(LingJing)导入修复工具")
    print("=" * 50)
    
    # 设置项目根目录
    project_dir = os.path.dirname(os.path.abspath(__file__))
    linjing_dir = os.path.join(project_dir, "linjing")
    
    if not os.path.exists(linjing_dir):
        print(f"错误: 找不到项目目录 {linjing_dir}")
        return
    
    print(f"项目目录: {linjing_dir}")
    
    # 确保utils/singleton.py存在
    created = create_utils_singleton(linjing_dir)
    if created:
        print("已创建singleton工具模块")
    
    # 修复导入（可能需要多次运行才能完全修复）
    for i in range(3):
        print(f"第 {i+1} 轮修复...")
        fixed_count = fix_imports_in_directory(linjing_dir)
        print(f"本轮修复了 {fixed_count} 个文件")
        if fixed_count == 0:
            break
    
    print("=" * 50)
    print("完成! 导入问题修复完毕")
    print("提示: 如果还有导入问题，可以尝试再次运行此脚本")

if __name__ == "__main__":
    main() 