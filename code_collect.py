#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
chat_image_generator 代码收集与分析工具
用于收集项目所有代码、分析项目结构和依赖关系
"""

import os
import sys
import json
import ast
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, Counter

# ==================== 配置 ====================
EXCLUDE_DIRS = [
    "__pycache__", "venv", ".git", "output", "logs", 
    ".pytest_cache", ".mypy_cache", "dist", "build",
    "*.egg-info", "tests"
]

EXCLUDE_FILES = [
    "*.pyc", "*.pyo", "*.pyd", "code_collect.py"
]

INCLUDE_EXTS = [".py", ".txt", ".md", ".json", ".yaml", ".yml"]

# ==================== 颜色输出 ====================
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_green(msg): print(f"{Colors.GREEN}{msg}{Colors.RESET}")
def print_red(msg): print(f"{Colors.RED}{msg}{Colors.RESET}")
def print_yellow(msg): print(f"{Colors.YELLOW}{msg}{Colors.RESET}")
def print_blue(msg): print(f"{Colors.BLUE}{msg}{Colors.RESET}")
def print_cyan(msg): print(f"{Colors.CYAN}{msg}{Colors.RESET}")
def print_magenta(msg): print(f"{Colors.MAGENTA}{msg}{Colors.RESET}")
def print_bold(msg): print(f"{Colors.BOLD}{msg}{Colors.RESET}")

# ==================== JSON 序列化辅助 ====================
class SetEncoder(json.JSONEncoder):
    """处理 set 类型的 JSON 编码器"""
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)

# ==================== 代码分析器 ====================
class CodeAnalyzer:
    """代码分析器"""
    
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.files: List[Path] = []
        self.file_stats: Dict = {}
        self.imports: Dict[str, Set[str]] = defaultdict(set)
        self.classes: Dict[str, List[str]] = defaultdict(list)
        self.functions: Dict[str, List[str]] = defaultdict(list)
        self.todo_comments: List[Tuple[str, str, str]] = []
        self.all_modules: Set[str] = set()
        self.third_party_imports: Set[str] = set()
        
    def scan(self) -> None:
        """扫描所有文件"""
        print_cyan("\n🔍 扫描项目文件...")
        
        for root, dirs, files in os.walk(self.root_dir):
            # 过滤目录
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
            
            for file in files:
                if self._should_include(file):
                    filepath = Path(root) / file
                    self.files.append(filepath)
        
        self.files.sort()
        print_green(f"   ✅ 找到 {len(self.files)} 个文件")
    
    def _should_include(self, filename: str) -> bool:
        """判断是否应该包含该文件"""
        # 检查排除模式
        for pattern in EXCLUDE_FILES:
            if pattern.startswith('*'):
                if filename.endswith(pattern[1:]):
                    return False
            elif filename == pattern:
                return False
        
        # 检查扩展名
        ext = Path(filename).suffix.lower()
        return ext in INCLUDE_EXTS
    
    def analyze(self) -> None:
        """分析所有文件"""
        print_cyan("\n📊 分析代码...")
        
        for filepath in self.files:
            ext = filepath.suffix.lower()
            if ext == '.py':
                self._analyze_python(filepath)
            elif ext in ['.txt', '.md']:
                self._analyze_text(filepath)
        
        print_green(f"   ✅ 分析完成")
    
    def _analyze_python(self, filepath: Path) -> None:
        """分析Python文件"""
        try:
            content = filepath.read_text(encoding='utf-8')
            rel_path = str(filepath.relative_to(self.root_dir))
            
            # 基本统计
            lines = content.splitlines()
            self.file_stats[rel_path] = {
                'size': filepath.stat().st_size,
                'lines': len(lines),
                'code_lines': len([l for l in lines if l.strip() and not l.strip().startswith('#')]),
                'comment_lines': len([l for l in lines if l.strip().startswith('#')]),
                'blank_lines': len([l for l in lines if not l.strip()]),
            }
            
            # 提取导入
            self._extract_imports(content, rel_path)
            
            # 提取类和函数
            try:
                tree = ast.parse(content)
                self._extract_classes_functions(tree, rel_path)
            except SyntaxError:
                pass
            
            # 提取TODO注释
            self._extract_todos(content, rel_path)
            
            # 模块名
            module_name = rel_path.replace('/', '.').replace('\\', '.').rsplit('.', 1)[0]
            self.all_modules.add(module_name)
            
        except Exception as e:
            print_yellow(f"   ⚠️ 无法分析 {filepath.name}: {e}")
    
    def _extract_imports(self, content: str, rel_path: str) -> None:
        """提取导入语句"""
        # 标准导入
        for match in re.finditer(r'^(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_.]*)', content, re.MULTILINE):
            module = match.group(1)
            if '.' in module:
                module = module.split('.')[0]
            self.imports[rel_path].add(module)
            
            # 判断是否为第三方库（不是相对导入，不是标准库）
            if not module.startswith('.'):
                # 标准库列表（简化版）
                stdlib = {'os', 'sys', 're', 'json', 'ast', 'pathlib', 'datetime', 
                         'typing', 'collections', 'itertools', 'functools', 'abc',
                         'dataclasses', 'enum', 'math', 'random', 'string', 'io',
                         'subprocess', 'threading', 'time', 'argparse', 'logging',
                         'tkinter', 'xml', 'html', 'urllib', 'http', 'email',
                         'base64', 'hashlib', 'hmac', 'tempfile', 'shutil',
                         'glob', 'fnmatch', 'pickle', 'shelve', 'sqlite3',
                         'zlib', 'gzip', 'zipfile', 'tarfile', 'csv', 'configparser',
                         'plistlib', 'netrc', 'getpass', 'curses', 'termios',
                         'pwd', 'grp', 'socket', 'ssl', 'select', 'asyncio',
                         'concurrent', 'multiprocessing', 'queue', 'weakref',
                         'copy', 'pprint', 'textwrap', 'traceback', 'warnings'}
                
                if module not in stdlib and not module.startswith('_'):
                    self.third_party_imports.add(module)
    
    def _extract_classes_functions(self, tree: ast.AST, rel_path: str) -> None:
        """提取类和函数定义"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self.classes[rel_path].append(node.name)
            elif isinstance(node, ast.FunctionDef):
                # 排除类内部方法（由类定义处理）
                if not any(isinstance(p, ast.ClassDef) for p in ast.walk(node) if p != node):
                    self.functions[rel_path].append(node.name)
    
    def _extract_todos(self, content: str, rel_path: str) -> None:
        """提取TODO注释"""
        for match in re.finditer(r'#\s*(TODO|FIXME|XXX|HACK|NOTE|BUG):?\s*(.*?)$', content, re.MULTILINE):
            self.todo_comments.append((rel_path, match.group(1), match.group(2).strip()))
    
    def _analyze_text(self, filepath: Path) -> None:
        """分析文本文件（非Python）"""
        try:
            content = filepath.read_text(encoding='utf-8')
            rel_path = str(filepath.relative_to(self.root_dir))
            
            self.file_stats[rel_path] = {
                'size': filepath.stat().st_size,
                'lines': len(content.splitlines()),
                'code_lines': 0,
                'comment_lines': 0,
                'blank_lines': 0,
            }
        except:
            pass
    
    def generate_report(self) -> Dict:
        """生成分析报告"""
        # 转换 set 为 list 以便 JSON 序列化
        return {
            'scan_time': datetime.now().isoformat(),
            'root_dir': str(self.root_dir),
            'total_files': len(self.files),
            'total_size': sum(f.stat().st_size for f in self.files),
            'file_stats': self.file_stats,
            'imports': {k: list(v) for k, v in self.imports.items()},
            'classes': dict(self.classes),
            'functions': dict(self.functions),
            'todo_comments': self.todo_comments,
            'all_modules': sorted(self.all_modules),
            'third_party_imports': sorted(self.third_party_imports),
            # 新增统计
            'summary': {
                'total_lines': sum(s['lines'] for s in self.file_stats.values()),
                'total_code_lines': sum(s['code_lines'] for s in self.file_stats.values()),
                'total_comment_lines': sum(s['comment_lines'] for s in self.file_stats.values()),
                'total_classes': sum(len(v) for v in self.classes.values()),
                'total_functions': sum(len(v) for v in self.functions.values()),
                'total_todos': len(self.todo_comments),
            }
        }
    
    def print_summary(self, report: Dict) -> None:
        """打印摘要"""
        print("\n" + "=" * 70)
        print_bold("📊 项目分析报告")
        print("=" * 70)
        
        # 基本统计
        print_cyan("\n📁 基本统计:")
        print(f"   总文件数: {report['total_files']}")
        print(f"   总大小: {report['total_size'] / 1024:.1f} KB")
        
        # 语言分布
        py_files = [f for f in self.files if f.suffix == '.py']
        other_files = [f for f in self.files if f.suffix != '.py']
        print(f"   Python文件: {len(py_files)}")
        print(f"   其他文件: {len(other_files)}")
        
        # 代码行数统计
        summary = report.get('summary', {})
        total_lines = summary.get('total_lines', 0)
        total_code = summary.get('total_code_lines', 0)
        total_comments = summary.get('total_comment_lines', 0)
        
        if total_lines > 0:
            print_cyan("\n📝 代码统计:")
            print(f"   总行数: {total_lines:,}")
            print(f"   代码行: {total_code:,} ({total_code/total_lines*100:.1f}%)")
            print(f"   注释行: {total_comments:,} ({total_comments/total_lines*100:.1f}%)")
        
        # 模块统计
        modules = report.get('all_modules', [])
        print_cyan(f"\n📦 模块统计:")
        print(f"   总模块数: {len(modules)}")
        
        # 前10个模块
        if modules:
            print("   主要模块:")
            for i, m in enumerate(modules[:10], 1):
                print(f"      {i:2d}. {m}")
            if len(modules) > 10:
                print(f"      ... 共 {len(modules)} 个")
        
        # 类和函数
        total_classes = summary.get('total_classes', 0)
        total_functions = summary.get('total_functions', 0)
        print_cyan(f"\n🏗️ 代码结构:")
        print(f"   类定义: {total_classes}")
        print(f"   函数定义: {total_functions}")
        
        # 第三方依赖
        third_party = report.get('third_party_imports', [])
        if third_party:
            print_cyan(f"\n📦 第三方依赖 ({len(third_party)}):")
            for dep in sorted(third_party)[:15]:
                print(f"   - {dep}")
            if len(third_party) > 15:
                print(f"   ... 共 {len(third_party)} 个")
        
        # TODO注释
        todos = report.get('todo_comments', [])
        if todos:
            print_yellow(f"\n📌 TODO/FIXME 注释 ({len(todos)}):")
            for rel_path, tag, comment in todos[:10]:
                print(f"   {tag}: {rel_path} -> {comment[:60]}")
            if len(todos) > 10:
                print(f"   ... 共 {len(todos)} 个")
        
        print("\n" + "=" * 70)


# ==================== 报告生成器 ====================
class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, root_dir: str, analyzer: CodeAnalyzer):
        self.root_dir = root_dir
        self.analyzer = analyzer
        self.report = analyzer.generate_report()
    
    def generate_markdown(self, output_path: str) -> None:
        """生成Markdown报告"""
        lines = []
        
        lines.append("# 📊 项目分析报告")
        lines.append(f"\n**生成时间**: {self.report['scan_time']}")
        lines.append(f"**项目目录**: `{self.report['root_dir']}`")
        
        # 基本统计
        lines.append("\n## 📁 基本统计")
        lines.append(f"- **总文件数**: {self.report['total_files']}")
        lines.append(f"- **总大小**: {self.report['total_size'] / 1024:.1f} KB")
        
        py_files = [f for f in self.analyzer.files if f.suffix == '.py']
        lines.append(f"- **Python文件**: {len(py_files)}")
        lines.append(f"- **其他文件**: {len(self.analyzer.files) - len(py_files)}")
        
        # 代码统计
        summary = self.report.get('summary', {})
        total_lines = summary.get('total_lines', 0)
        total_code = summary.get('total_code_lines', 0)
        total_comments = summary.get('total_comment_lines', 0)
        
        if total_lines > 0:
            lines.append("\n## 📝 代码统计")
            lines.append(f"- **总行数**: {total_lines:,}")
            lines.append(f"- **代码行**: {total_code:,} ({total_code/total_lines*100:.1f}%)")
            lines.append(f"- **注释行**: {total_comments:,} ({total_comments/total_lines*100:.1f}%)")
        
        # 文件列表
        lines.append("\n## 📄 文件列表")
        lines.append("\n| 文件 | 大小 | 行数 |")
        lines.append("|------|------|------|")
        
        for rel_path, stats in sorted(self.report['file_stats'].items()):
            size_kb = stats['size'] / 1024
            lines.append(f"| `{rel_path}` | {size_kb:.1f} KB | {stats['lines']} |")
        
        # 第三方依赖
        third_party = self.report.get('third_party_imports', [])
        if third_party:
            lines.append("\n## 📦 第三方依赖")
            for dep in sorted(third_party):
                lines.append(f"- `{dep}`")
        
        # 模块列表
        modules = self.report.get('all_modules', [])
        if modules:
            lines.append("\n## 📦 模块列表")
            for m in sorted(modules):
                lines.append(f"- `{m}`")
        
        # 类和函数
        classes = self.report.get('classes', {})
        if classes:
            lines.append("\n## 🏗️ 类定义")
            for rel_path, names in sorted(classes.items()):
                lines.append(f"- `{rel_path}`: {', '.join(names)}")
        
        # TODO
        todos = self.report.get('todo_comments', [])
        if todos:
            lines.append("\n## 📌 TODO/FIXME")
            for rel_path, tag, comment in todos:
                lines.append(f"- **{tag}** in `{rel_path}`: {comment}")
        
        # 写入文件
        Path(output_path).write_text("\n".join(lines), encoding='utf-8')
        print_green(f"\n✅ Markdown报告已生成: {output_path}")
    
    def generate_json(self, output_path: str) -> None:
        """生成JSON报告 - 使用自定义编码器"""
        Path(output_path).write_text(
            json.dumps(self.report, indent=2, ensure_ascii=False, cls=SetEncoder),
            encoding='utf-8'
        )
        print_green(f"✅ JSON报告已生成: {output_path}")
    
    def generate_snapshot(self, output_path: str) -> None:
        """生成代码快照（类似原项目的snapshot）"""
        lines = []
        
        lines.append("=" * 80)
        lines.append(f"项目快照 - chat_image_generator")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"源目录: {self.root_dir}")
        lines.append(f"文件总数: {len(self.analyzer.files)}")
        lines.append("=" * 80)
        lines.append("")
        
        # 目录结构
        lines.append("📁 目录结构:")
        lines.append("-" * 40)
        
        # 生成目录树
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
            level = root.replace(str(self.root_dir), '').count(os.sep)
            indent = '│   ' * level
            if level > 0:
                lines.append(f"{indent}├── {os.path.basename(root)}/")
            
            # 过滤并排序文件
            valid_files = [f for f in files if self.analyzer._should_include(f)]
            for i, filename in enumerate(sorted(valid_files)):
                is_last = (i == len(valid_files) - 1)
                prefix = "└── " if is_last else "├── "
                lines.append(f"{indent}│   {prefix}{filename}")
        
        lines.append("\n" + "=" * 80)
        lines.append("📄 文件内容:")
        lines.append("=" * 80)
        lines.append("")
        
        # 写入每个文件内容（仅Python文件）
        for filepath in sorted(self.analyzer.files):
            if filepath.suffix != '.py':
                continue
            try:
                content = filepath.read_text(encoding='utf-8')
                rel_path = filepath.relative_to(self.root_dir)
                
                lines.append("\n" + "=" * 80)
                lines.append(f"📄 文件: {rel_path}")
                lines.append("=" * 80)
                lines.append("")
                lines.append(content)
                lines.append("")
            except:
                pass
        
        Path(output_path).write_text("\n".join(lines), encoding='utf-8')
        print_green(f"✅ 快照已生成: {output_path}")


# ==================== 主函数 ====================
def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="代码收集与分析工具")
    parser.add_argument("--dir", "-d", type=str, default=".",
                       help="项目目录 (默认: 当前目录)")
    parser.add_argument("--output", "-o", type=str, default="analysis_report",
                       help="输出文件前缀 (默认: analysis_report)")
    parser.add_argument("--format", "-f", choices=['all', 'json', 'md', 'snapshot'],
                       default='all', help="输出格式 (默认: all)")
    
    args = parser.parse_args()
    
    # 确定项目目录
    project_dir = args.dir
    if project_dir == ".":
        project_dir = os.getcwd()
    
    if not os.path.exists(project_dir):
        print_red(f"❌ 目录不存在: {project_dir}")
        sys.exit(1)
    
    print_bold("\n🔍 代码收集与分析工具")
    print("=" * 60)
    print(f"📁 项目目录: {project_dir}")
    print("=" * 60)
    
    # 分析
    analyzer = CodeAnalyzer(project_dir)
    analyzer.scan()
    analyzer.analyze()
    
    # 生成报告
    report_gen = ReportGenerator(project_dir, analyzer)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.format in ['all', 'md']:
        report_gen.generate_markdown(f"{args.output}_{timestamp}.md")
    
    if args.format in ['all', 'json']:
        report_gen.generate_json(f"{args.output}_{timestamp}.json")
    
    if args.format in ['all', 'snapshot']:
        report_gen.generate_snapshot(f"project_snapshot_{timestamp}.txt")
    
    # 打印摘要
    analyzer.print_summary(report_gen.report)
    
    print_cyan("\n💡 使用建议:")
    print("   - 查看 *.md 文件了解项目概览")
    print("   - 查看 *.json 文件获取结构化数据")
    print("   - 查看 project_snapshot_*.txt 获取完整代码快照")


if __name__ == "__main__":
    main()