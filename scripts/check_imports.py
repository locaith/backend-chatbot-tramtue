#!/usr/bin/env python3
"""
Import check script để đảm bảo tất cả modules có syntax đúng và import cơ bản
"""

import sys
import ast
import traceback
from pathlib import Path

def check_syntax(file_path: Path) -> bool:
    """Kiểm tra syntax của file Python"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse AST để kiểm tra syntax
        ast.parse(content, filename=str(file_path))
        print(f"✅ {file_path}")
        return True
    except SyntaxError as e:
        print(f"❌ {file_path}: Syntax Error - {e}")
        return False
    except Exception as e:
        print(f"❌ {file_path}: {e}")
        return False

def check_basic_imports(file_path: Path) -> bool:
    """Kiểm tra các import cơ bản trong file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Kiểm tra các import statement
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Chỉ kiểm tra import từ app module
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith('app.'):
                        # Kiểm tra xem module được import có tồn tại không
                        module_parts = node.module.split('.')
                        if len(module_parts) >= 2:
                            # app.core.config -> app/core/config.py
                            module_path = Path('app') / '/'.join(module_parts[1:])
                            py_file = module_path.with_suffix('.py')
                            init_file = module_path / '__init__.py'
                            
                            if not (py_file.exists() or init_file.exists()):
                                 print(f"⚠️  {file_path}: Missing module {node.module}")
                                 return False
        
        return True
    except Exception as e:
        print(f"❌ {file_path}: Import check failed - {e}")
        return False

def main():
    """Main function để check tất cả Python files"""
    print("🔍 Checking Python files syntax and imports...")
    print("=" * 60)
    
    # Tìm tất cả Python files trong app directory
    app_dir = Path("app")
    python_files = list(app_dir.rglob("*.py"))
    
    syntax_success = 0
    import_success = 0
    total_files = len(python_files)
    
    print("📝 Syntax Check:")
    print("-" * 30)
    for py_file in python_files:
        if check_syntax(py_file):
            syntax_success += 1
    
    print("\n📦 Import Check:")
    print("-" * 30)
    for py_file in python_files:
        if check_basic_imports(py_file):
            import_success += 1
    
    print("=" * 60)
    print(f"📊 Syntax Results: {syntax_success}/{total_files} files passed")
    print(f"📊 Import Results: {import_success}/{total_files} files passed")
    
    if syntax_success == total_files and import_success == total_files:
        print("🎉 All checks passed!")
        return 0
    else:
        print("💥 Some checks failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())