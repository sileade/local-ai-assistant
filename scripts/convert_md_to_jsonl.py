#!/usr/bin/env python3
"""
Конвертер Markdown-документов (экспорт scoliologic.ru) в обучающий датасет (JSONL).
Разбивает большие документы на логические блоки (Q&A) для обучения моделей.
"""

import os
import json
import re
import glob

def extract_qa_pairs(md_content, filename):
    """Извлекает пары вопрос-ответ из Markdown документа."""
    pairs = []
    
    # Разбиваем по заголовкам
    sections = re.split(r'\n(#{1,3})\s+', md_content)
    
    if len(sections) < 3:
        # Если нет заголовков, берем весь текст
        if len(md_content.strip()) > 100:
            pairs.append({
                "query": f"Расскажи про {os.path.basename(filename).replace('.md', '')}",
                "response": md_content.strip(),
                "expert": "sysadmin" if "GT 01" in filename or "Devops" in filename else "general",
                "quality": 0.9,
                "tags": ["knowledge_base", "scoliologic"]
            })
        return pairs

    # Первый элемент - текст до первого заголовка
    current_title = os.path.basename(filename).replace('.md', '')
    
    for i in range(1, len(sections), 2):
        level = len(sections[i])
        title = sections[i+1].split('\n')[0].strip()
        content = '\n'.join(sections[i+1].split('\n')[1:]).strip()
        
        if len(content) > 50:
            # Формируем вопрос на основе заголовка
            query = f"Что известно про {title} в контексте {current_title}?"
            if "?" in title:
                query = title
                
            expert = "sysadmin" if "GT 01" in filename or "Devops" in filename else "general"
            
            pairs.append({
                "query": query,
                "response": content,
                "expert": expert,
                "quality": 0.9,
                "tags": ["knowledge_base", "scoliologic", f"level_{level}"]
            })
            
    return pairs

def main():
    export_dir = "/home/ubuntu/scoliologic-export"
    output_file = "/home/ubuntu/sclg-ai-repo/training/scoliologic_kb.jsonl"
    
    md_files = glob.glob(f"{export_dir}/**/*.md", recursive=True)
    print(f"Найдено {len(md_files)} Markdown файлов.")
    
    all_pairs = []
    for file_path in md_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            pairs = extract_qa_pairs(content, file_path)
            all_pairs.extend(pairs)
            print(f"Извлечено {len(pairs)} пар из {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Ошибка при обработке {file_path}: {e}")
            
    print(f"\nВсего извлечено {len(all_pairs)} пар вопрос-ответ.")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for pair in all_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + '\n')
            
    print(f"Датасет сохранен в {output_file}")
    print("Для добавления в основную базу используйте: cat training/scoliologic_kb.jsonl >> training/golden_dataset.jsonl")

if __name__ == "__main__":
    main()
