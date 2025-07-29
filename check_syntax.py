#!/usr/bin/env python3
"""
Скрипт для проверки синтаксиса всех модулей FOGO Bot
"""

import ast
import os
import sys

def check_syntax(filename):
    """Проверяет синтаксис Python файла"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Компилируем код
        ast.parse(source, filename=filename)
        print(f"✅ {filename} - синтаксис корректный")
        return True
        
    except SyntaxError as e:
        print(f"❌ {filename} - синтаксическая ошибка:")
        print(f"   Строка {e.lineno}: {e.text.strip() if e.text else 'N/A'}")
        print(f"   Ошибка: {e.msg}")
        return False
        
    except FileNotFoundError:
        print(f"⚠️  {filename} - файл не найден")
        return False
        
    except Exception as e:
        print(f"❌ {filename} - ошибка: {e}")
        return False

def main():
    """Проверяет все модули проекта"""
    print("🔍 Проверка синтаксиса модулей FOGO Bot")
    print("=" * 50)
    
    # Список файлов для проверки
    files_to_check = [
        'config.py',
        'utils.py', 
        'network.py',
        'airdrop.py',
        'transaction.py',
        'swap.py',
        'worker.py',
        'main.py'
    ]
    
    all_good = True
    
    for filename in files_to_check:
        if not check_syntax(filename):
            all_good = False
    
    print("=" * 50)
    
    if all_good:
        print("🎉 Все файлы имеют корректный синтаксис!")
        return 0
    else:
        print("💥 Найдены синтаксические ошибки!")
        return 1

if __name__ == "__main__":
    sys.exit(main())