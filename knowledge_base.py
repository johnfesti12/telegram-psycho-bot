import os
import re
import logging
import PyPDF2
import docx
from database import SubscriptionManager
import requests
import numpy as np
import json
import ssl
import urllib3

# Фикс для SSL ошибок
os.environ['CURL_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class PsychologyKnowledgeBase:
    def __init__(self, books_dir="books"):
        self.books_dir = books_dir
        self.knowledge_base = {}
        self.embeddings_cache = {}
        self.precomputed_embeddings = {}  

        self.api_key = self._load_api_key()
        
        self.load_books()
        self.load_precomputed_embeddings()  

    def _load_api_key(self):
        """Загрузка API ключа из переменных окружения"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if not api_key:
                print("❌ DEEPSEEK_API_KEY не найден в .env файле")
                return None
            
            print(f"✅ API ключ загружен (длина: {len(api_key)})")
            return api_key
            
        except Exception as e:
            print(f"❌ Ошибка загрузки API ключа: {e}")
            return None
    
    def cosine_similarity(self, vec1, vec2):
        """Простая реализация косинусной схожести без sklearn"""
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            return dot_product / (norm1 * norm2)
        except:
            return 0

    def get_embedding(self, text):
        """Получение вектора через DeepSeek Chat Completions"""
        try:
            # Проверяем кэш
            cache_key = text[:100]
            if cache_key in self.embeddings_cache:
                return self.embeddings_cache[cache_key]
            
            # ПРОВЕРЯЕМ ЧТО API КЛЮЧ ЕСТЬ
            if not self.api_key:
                print("⚠️ API ключ не загружен, использую fallback")
                return self._create_fallback_embedding(text)
            
            # Правильный эндпоинт для DeepSeek
            url = "https://api.deepseek.com/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",  # ИСПОЛЬЗУЕМ self.api_key
                "Content-Type": "application/json"
            }   
            
            # Создаем промпт для генерации числового представления текста
            prompt = f"""
            Создай числовой вектор-представление для следующего текста. 
            Верни ТОЛЬКО числа через запятую, без пояснений.
            
            Текст: "{text}"
            
            Вектор (100 чисел от 0 до 1):
            """
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 400,
                "temperature": 0.1
            }
            
            print(f"🔗 Отправляю запрос к DeepSeek для: {text[:50]}...")
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                # Парсим числа из ответа
                numbers = []
                for part in content.split(','):
                    part = part.strip()
                    try:
                        num = float(part)
                        numbers.append(num)
                    except:
                        continue
                
                # Если получили числа, используем их
                if numbers:
                    # Нормализуем до 100 элементов
                    if len(numbers) < 100:
                        numbers.extend([0] * (100 - len(numbers)))
                    else:
                        numbers = numbers[:100]
                    
                    # Нормализуем вектор
                    vector = np.array(numbers, dtype=np.float32)
                    norm = np.linalg.norm(vector)
                    if norm > 0:
                        vector = vector / norm
                    
                    self.embeddings_cache[cache_key] = vector
                    print(f"✅ Получен эмбединг через Chat API для: {text[:50]}...")
                    return vector
                
                # Если не получилось распарсить, создаем fallback вектор
                print("⚠️ Не удалось распарсить вектор, создаю fallback...")
                return self._create_fallback_embedding(text)
                
            else:
                print(f"❌ Ошибка API: {response.status_code} - {response.text}")
                return self._create_fallback_embedding(text)
                    
        except Exception as e:
            print(f"❌ Ошибка получения эмбединга: {e}")
            return self._create_fallback_embedding(text)

    def _create_fallback_embedding(self, text):
        """Создание fallback вектора если API не работает"""
        # Используем улучшенную локальную версию
        text_lower = text.lower()
        
        psychology_keywords = [
            'эмоц', 'чувств', 'психолог', 'терапи', 'личность', 'сознание',
            'бессознательн', 'тревож', 'страх', 'депресси', 'отношен', 
            'общен', 'коммуникац', 'мысл', 'поведен', 'управлен', 'стресс'
        ]
        
        vector = []
        
        # Базовые характеристики
        vector.extend([
            len(text) / 1000.0,           # нормализованная длина
            len(text.split()) / 100.0,    # нормализованное кол-во слов
            text.count('.') / 10.0,       # нормализованное кол-во предложений
        ])
        
        # Частоты ключевых слов
        for keyword in psychology_keywords:
            count = text_lower.count(keyword)
            vector.append(min(count / 5.0, 1.0))  # нормализуем до 0-1
        
        # Хеш текста для уникальности
        import hashlib
        text_hash = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        for i in range(20):
            vector.append(((text_hash >> (i * 3)) & 7) / 7.0)
        
        # Добиваем до 100 элементов
        while len(vector) < 100:
            vector.append(0.0)
        
        vector = vector[:100]
        vector = np.array(vector, dtype=np.float32)
        
        # Нормализуем
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        print(f"✅ Создан fallback эмбединг для: {text[:50]}...")
        return vector
                
    def semantic_search(self, query, max_results=3):
        """Семантический поиск по ВСЕМ книгам"""
        try:
            print(f"🔍 Семантический поиск: {query}")
            
            # Получаем вектор запроса
            query_embedding = self.get_embedding(query)
            if query_embedding is None:
                print("⚠️ Использую обычный поиск (эмбединг не получен)")
                return self.search_in_books(query, max_results)
            
            results = []
            query_embedding = np.array(query_embedding)
            
            # СБОР ФРАГМЕНТОВ ИЗ ВСЕХ КНИГ
            for book_name, book_data in self.knowledge_base.items():
                print(f"📖 Обрабатываю книгу: {book_name}")
                content = book_data['content']
                
                # Разбиваем на предложения (БОЛЬШЕ предложений)
                sentences = self.split_into_sentences(content)
                
                # Берем больше предложений из каждой книги
                for sentence in sentences[:50]:  # Увеличил с 15 до 50
                    if len(sentence) > 20:
                        sentence_embedding = self.get_embedding(sentence)
                        
                        if sentence_embedding is not None:
                            sentence_embedding = np.array(sentence_embedding)
                            
                            # Косинусная схожесть
                            similarity = np.dot(query_embedding, sentence_embedding) / (
                                np.linalg.norm(query_embedding) * np.linalg.norm(sentence_embedding)
                            )
                            
                            if similarity > 0.05:  # Понизил порог для большего охвата
                                results.append({
                                    'book': book_name,
                                    'text': sentence,
                                    'similarity': float(similarity)
                                })
                
                # НЕ ВЫХОДИМ РАНЬШЕ - обрабатываем ВСЕ книги
                # if len(results) >= max_results * 2:  # ← УБРАТЬ ЭТО!
                #     break
            
            # Гарантируем разнообразие источников
            diverse_results = self.ensure_diversity(results, max_results)
            
            if diverse_results:
                books_used = set(r['book'] for r in diverse_results)
                print(f"✅ Найдено {len(diverse_results)} фрагментов из {len(books_used)} книг: {books_used}")
            else:
                print("⚠️ По семантическому поиску ничего не найдено")
                return self.search_in_books(query, max_results)
                
            return diverse_results
            
        except Exception as e:
            print(f"❌ Ошибка семантического поиска: {e}")
            return self.search_in_books(query, max_results)

    def ensure_diversity(self, results, max_results, max_per_book=2):
        """Гарантирует, что результаты будут из разных книг"""
        if not results:
            return []
        
        # Группируем по книгам
        book_groups = {}
        for result in results:
            book = result['book']
            if book not in book_groups:
                book_groups[book] = []
            book_groups[book].append(result)
        
        # Сортируем каждую группу по схожести
        for book in book_groups:
            book_groups[book].sort(key=lambda x: x['similarity'], reverse=True)
        
        # Берем лучшие из каждой книги
        diverse_results = []
        for book in book_groups:
            diverse_results.extend(book_groups[book][:max_per_book])
        
        # Сортируем общий список по схожести
        diverse_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        return diverse_results[:max_results]

    def split_into_sentences(self, text):
        """Простое разделение на предложения"""
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def load_books(self):
        """Загрузка книг из папки books"""
        books_dir = "./books"
        if not os.path.exists(books_dir):
            os.makedirs(books_dir)
            print("📁 Создана папка 'books'. Добавьте туда книги в формате PDF, TXT или DOCX!")
            return
        
        supported_files = []
        for filename in os.listdir(books_dir):
            if filename.lower().endswith(('.pdf', '.txt', '.docx')):
                supported_files.append(filename)
        
        if not supported_files:
            print("📚 В папке 'books' нет поддерживаемых файлов (PDF, TXT, DOCX)")
            return
        
        print(f"📖 Найдено книг: {len(supported_files)}")
        
        for filename in supported_files:
            file_path = os.path.join(books_dir, filename)
            try:
                if filename.lower().endswith('.pdf'):
                    text = self.read_pdf(file_path)
                elif filename.lower().endswith('.docx'):
                    text = self.read_docx(file_path)
                else:  # txt
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                
                if text:
                    self.knowledge_base[filename] = {
                        'content': text,
                        'type': filename.split('.')[-1].upper()
                    }
                    print(f"✅ Загружена: {filename} ({len(text)} символов)")
                else:
                    print(f"❌ Не удалось прочитать: {filename}")
                    
            except Exception as e:
                print(f"❌ Ошибка загрузки {filename}: {e}")
    
    def read_pdf(self, file_path):
        """Чтение PDF файлов с обработкой ошибок"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
        except Exception as e:
            print(f"Ошибка чтения PDF {file_path}: {e}")
            # Попробуем альтернативный метод
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except:
                pass
        
        return text
    
    def read_docx(self, file_path):
        """Чтение DOCX файлов"""
        text = ""
        try:
            doc = docx.Document(file_path)
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
        except Exception as e:
            print(f"Ошибка чтения DOCX {file_path}: {e}")
        
        return text
    
    def search_in_books(self, query, max_results=3):
        """Поиск релевантной информации в книгах"""
        if not self.knowledge_base:
            return "📚 Библиотека пуста. Добавьте книги в папку 'books'."
        
        query_lower = query.lower()
        relevant_results = []
        
        for book_name, book_data in self.knowledge_base.items():
            content = book_data['content']
            content_lower = content.lower()
            
            # Ищем вхождения запроса
            if query_lower in content_lower:
                # Находим позицию первого вхождения
                index = content_lower.find(query_lower)

                # Берем контекст вокруг найденного фрагмента
                start = max(0, index - 150)
                end = min(len(content), index + 350)
                
                excerpt = content[start:end]
                
                # Очищаем и форматируем текст
                excerpt = self.clean_text(excerpt)
                
                relevant_results.append({
                    'book': book_name,
                    'excerpt': excerpt,
                    'position': index
                })
            
            if len(relevant_results) >= max_results:
                break
        
        if not relevant_results:
            return "🔍 В библиотеке нет информации по вашему запросу."
        
        # Форматируем результаты
        result_text = "📚 <b>Найдено в библиотеке:</b>\n\n"
        for i, result in enumerate(relevant_results, 1):
            result_text += f"<b>{i}. {result['book']}</b>\n"
            result_text += f"<i>{result['excerpt']}...</i>\n\n"
        
        return result_text
    
    def clean_text(self, text):
        """Очистка текста от лишних пробелов и переносов"""
        # Заменяем множественные переносы и пробелы
        import re
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()
    
    def get_library_info(self):
        """Информация о библиотеке"""
        if not self.knowledge_base:
            return "📚 Библиотека пуста"
        
        total_books = len(self.knowledge_base)
        book_types = {}
        
        for book_data in self.knowledge_base.values():
            book_type = book_data['type']
            book_types[book_type] = book_types.get(book_type, 0) + 1
        
        type_info = ", ".join([f"{count} {typ}" for typ, count in book_types.items()])
        
        return f"📚 Библиотека: {total_books} книг ({type_info})"
    
    def format_semantic_results(self, results):
        """Форматирование результатов"""
        if not results:
            return ""
        
        result_text = "📚 <b>Найдено по смыслу:</b>\n\n"
        
        for i, result in enumerate(results, 1):
            similarity_percent = int(result['similarity'] * 100)
            text_preview = result['text'][:200] + "..." if len(result['text']) > 200 else result['text']
            result_text += f"<b>{i}. {result['book']}</b> ({similarity_percent}%)\n"
            result_text += f"<i>{text_preview}</i>\n\n"
        
        return result_text

    def get_context_for_ai(self, query, max_excerpts=18):        
        """Получение релевантного контекста из книг для AI"""
        if not self.knowledge_base:
            return ""
        
        query_lower = query.lower()
        query_words = [word for word in query_lower.split() if len(word) > 3]  # Фильтруем короткие слова
        relevant_excerpts = []
        
        for book_name, book_data in self.knowledge_base.items():
            content = book_data['content']
            content_lower = content.lower()
            
            # Считаем релевантность по ключевым словам
            relevance_score = sum(1 for word in query_words if word in content_lower)
            
            if relevance_score > 0:
                # Находим наиболее релевантный отрывок
                paragraphs = content.split('\n\n')  # Разделяем на параграфы
                
                for paragraph in paragraphs:
                    if any(word in paragraph.lower() for word in query_words):
                        # Ограничиваем длину отрывка
                        if len(paragraph) > 500:
                            paragraph = paragraph[:500] + "..."
                        
                        relevant_excerpts.append({
                            'book': book_name,
                            'text': paragraph.strip(),
                            'score': relevance_score
                        })
                        break  # Берем только один отрывок из каждой книги
            
            if len(relevant_excerpts) >= max_excerpts:
                break
        
        # Сортируем по релевантности
        relevant_excerpts.sort(key=lambda x: x['score'], reverse=True)
        
        # Форматируем для AI
        if relevant_excerpts:
            context_text = "РЕЛЕВАНТНАЯ ИНФОРМАЦИЯ ИЗ ПСИХОЛОГИЧЕСКОЙ ЛИТЕРАТУРЫ:\n\n"
            for excerpt in relevant_excerpts:
                context_text += f"📖 Из книги '{excerpt['book']}':\n{excerpt['text']}\n\n"
            
            return context_text.strip()
        
        return ""
    
    def load_precomputed_embeddings(self):
        """Загрузка предварительно вычисленных эмбеддингов"""
        try:
            if os.path.exists('precomputed_embeddings.json'):
                with open('precomputed_embeddings.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Конвертируем обратно в numpy arrays
                for book_name, embeddings in data.items():
                    self.precomputed_embeddings[book_name] = []
                    for item in embeddings:
                        self.precomputed_embeddings[book_name].append({
                            'text': item['text'],
                            'embedding': np.array(item['embedding'])
                        })
                
                print(f"✅ Загружено предварительных эмбеддингов: {sum(len(emb) for emb in self.precomputed_embeddings.values())}")
            else:
                print("⚠️ Файл с предварительными эмбеддингами не найден")
        except Exception as e:
            print(f"❌ Ошибка загрузки предварительных эмбеддингов: {e}")

    def fast_semantic_search(self, query, max_results=5):
        """БЫСТРЫЙ поиск с предварительными эмбеддингами"""
        try:
            print(f"🔍 Быстрый семантический поиск: {query}")
            
            # Получаем вектор запроса (единственный вызов API)
            query_embedding = self.get_embedding(query)
            if query_embedding is None:
                print("⚠️ Использую обычный поиск")
                return self.search_in_books(query, max_results)
            
            query_embedding = np.array(query_embedding)
            results = []
            
            # Ищем по предварительным эмбеддингам
            for book_name, chunks in self.precomputed_embeddings.items():
                for chunk_data in chunks:
                    chunk_embedding = chunk_data['embedding']
                    chunk_text = chunk_data['text']
                    
                    similarity = np.dot(query_embedding, chunk_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
                    )
                    
                    if similarity > 0.1:
                        results.append({
                            'book': book_name,
                            'text': chunk_text,
                            'similarity': float(similarity)
                        })
            
            # Гарантируем разнообразие
            diverse_results = self.ensure_diversity(results, max_results)
            
            if diverse_results:
                books_used = set(r['book'] for r in diverse_results)
                print(f"✅ Найдено {len(diverse_results)} фрагментов из {len(books_used)} книг")
            
            return diverse_results[:max_results]
            
        except Exception as e:
            print(f"❌ Ошибка быстрого поиска: {e}")
            return self.search_in_books(query, max_results)