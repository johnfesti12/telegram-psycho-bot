import os
import logging
import PyPDF2
import docx
from database import SubscriptionManager

logger = logging.getLogger(__name__)

class PsychologyKnowledgeBase:
    def __init__(self, subscription_manager):
        self.sub_manager = subscription_manager
        self.knowledge_base = {}
        self.load_books()
    
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