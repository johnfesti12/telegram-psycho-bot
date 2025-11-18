import os
import json
import numpy as np
import time
import requests
from knowledge_base import PsychologyKnowledgeBase

def full_api_precompute():
    print("🚀 ЗАПУСК ПОЛНОЦЕННОЙ ПРЕДОБРАБОТКИ С DEEPSEEK API")
    print("=" * 60)
    
    try:
        kb = PsychologyKnowledgeBase()
        
        print(f"📚 Найдено книг: {len(kb.knowledge_base)}")
        for book_name in kb.knowledge_base.keys():
            print(f"   • {book_name}")
        
        all_embeddings = {}
        total_processed = 0
        failed_chunks = 0
        
        # Обрабатываем каждую книгу
        for book_idx, (book_name, book_data) in enumerate(kb.knowledge_base.items(), 1):
            print(f"\n📖 [{book_idx}/{len(kb.knowledge_base)}] Обрабатываю книгу: {book_name}")
            content = book_data['content']
            
            # Разбиваем на chunks
            chunks = kb.split_into_sentences(content)
            print(f"   📄 Найдено {len(chunks)} предложений")
            
            book_embeddings = []
            
            # Обрабатываем chunks (больше чем в упрощенной версии)
            chunks_to_process = chunks[:50]  # По 50 chunks на книгу
            
            for i, chunk in enumerate(chunks_to_process, 1):
                if len(chunk) > 25:  # Более строгий фильтр
                    print(f"   🔄 [{i}/{len(chunks_to_process)}] Обрабатываю: {chunk[:70]}...")
                    
                    try:
                        embedding = kb.get_embedding(chunk)
                        
                        if embedding is not None:
                            book_embeddings.append({
                                'text': chunk,
                                'embedding': embedding.tolist()
                            })
                            total_processed += 1
                            print(f"   ✅ Успешно (всего: {total_processed})")
                        else:
                            failed_chunks += 1
                            print(f"   ❌ Не удалось получить эмбеддинг")
                    
                    except Exception as e:
                        failed_chunks += 1
                        print(f"   ❌ Ошибка обработки: {e}")
                    
                    # Пауза между запросами чтобы не превысить лимиты
                    print("   ⏳ Пауза 2 секунды...")
                    time.sleep(2)
            
            all_embeddings[book_name] = book_embeddings
            print(f"   📊 Книга '{book_name}' завершена: {len(book_embeddings)} эмбеддингов")
            
            # Сохраняем промежуточный результат после каждой книги
            with open('precomputed_embeddings.json', 'w', encoding='utf-8') as f:
                json.dump(all_embeddings, f, ensure_ascii=False, indent=2)
            print("   💾 Промежуточное сохранение...")
        
        # Финальное сохранение
        with open('precomputed_embeddings.json', 'w', encoding='utf-8') as f:
            json.dump(all_embeddings, f, ensure_ascii=False, indent=2)
        
        # Статистика
        print("\n" + "=" * 60)
        print("🎉 ПРЕДОБРАБОТКА ЗАВЕРШЕНА!")
        print(f"📊 Статистика:")
        print(f"   • Обработано книг: {len(all_embeddings)}")
        print(f"   • Создано эмбеддингов: {total_processed}")
        print(f"   • Неудачных chunks: {failed_chunks}")
        
        # Детальная статистика по книгам
        print(f"\n📚 Детали по книгам:")
        for book_name, embeddings in all_embeddings.items():
            print(f"   • {book_name}: {len(embeddings)} эмбеддингов")
        
        print(f"\n✅ Файл 'precomputed_embeddings.json' готов к использованию!")
        print("🔁 Перезапустите бота для применения изменений.")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        print(f"🔍 Детали: {traceback.format_exc()}")

if __name__ == "__main__":
    full_api_precompute()