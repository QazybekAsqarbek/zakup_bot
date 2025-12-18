import io
import docx
import logging

logger = logging.getLogger(__name__)

def extract_text_from_file(file_bytes, mime_type, file_name=""):
    """
    Извлекает текст из разных форматов файлов.
    """
    try:
        # 1. Markdown / Txt / CSV
        if mime_type in ['text/markdown', 'text/plain', 'text/csv'] or file_name.endswith(('.md', '.txt', '.csv')):
            return file_bytes.decode('utf-8')
        
        # 2. Word (.docx)
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            doc = docx.Document(io.BytesIO(file_bytes))
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            # Также можно достать таблицы из Word, если нужно
            return "\n".join(full_text)

        # 3. Excel (.xlsx) - простая выжимка
        # (для сложных таблиц лучше отправлять скриншот или csv, но попробуем текст)
        elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            import pandas as pd
            df = pd.read_excel(io.BytesIO(file_bytes))
            return df.to_string()

        else:
            logger.warning(f"No text extractor for {mime_type}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting text from file: {e}")
        return None
