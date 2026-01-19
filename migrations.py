"""
Database Migration System

Manages versioned database schema migrations.
Each migration is applied in a transaction and recorded in schema_migrations table.
"""
import os
import re
import logging
from pathlib import Path
from typing import List, Set, Optional
import asyncpg

logger = logging.getLogger(__name__)

# Путь к папке с миграциями
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def ensure_migrations_table(conn: asyncpg.Connection):
    """
    Создать таблицу schema_migrations, если её нет
    
    Args:
        conn: Соединение с БД
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


async def get_applied_migrations(conn: asyncpg.Connection) -> Set[str]:
    """
    Получить список применённых миграций
    
    Args:
        conn: Соединение с БД
        
    Returns:
        Множество версий применённых миграций
    """
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {row["version"] for row in rows}


def get_migration_files() -> List[tuple[str, Path]]:
    """
    Получить список файлов миграций, отсортированных по версии
    
    Returns:
        Список кортежей (version, path), отсортированный по version
    """
    if not MIGRATIONS_DIR.exists():
        logger.warning(f"Migrations directory not found: {MIGRATIONS_DIR}")
        return []
    
    migrations = []
    pattern = re.compile(r'^(\d+)_(.+)\.sql$')
    
    for file_path in MIGRATIONS_DIR.glob("*.sql"):
        match = pattern.match(file_path.name)
        if match:
            version = match.group(1)
            migrations.append((version, file_path))
        else:
            logger.warning(f"Migration file name doesn't match pattern: {file_path.name}")
    
    # Сортируем по числовому значению версии (не лексикографически)
    migrations.sort(key=lambda x: int(x[0]))
    
    return migrations


async def apply_migration(conn: asyncpg.Connection, version: str, migration_path: Path) -> bool:
    """
    Применить одну миграцию в транзакции
    
    Args:
        conn: Соединение с БД (уже в транзакции)
        version: Версия миграции (например, "001")
        migration_path: Путь к SQL файлу миграции
        
    Returns:
        True если миграция применена успешно, False если ошибка
        
    Raises:
        Exception: При ошибке выполнения SQL
    """
    try:
        # Читаем SQL из файла
        sql_content = migration_path.read_text(encoding='utf-8')
        
        if not sql_content.strip():
            logger.warning(f"Migration {version} is empty, skipping")
            return True
        
        logger.info(f"Applying migration {version}: {migration_path.name}")
        
        # Выполняем SQL в транзакции
        # asyncpg.execute может выполнить только одну команду за раз
        # Разделяем SQL на отдельные команды по точке с запятой
        
        # Парсер SQL команд с поддержкой dollar-quoted строк (DO $$ ... $$)
        commands = []
        current_command = []
        in_single_quote = False
        in_double_quote = False
        in_dollar_quote = False
        dollar_tag = None
        i = 0
        
        while i < len(sql_content):
            char = sql_content[i]
            current_command.append(char)
            
            if not in_single_quote and not in_double_quote and not in_dollar_quote:
                # Проверяем начало dollar-quoted строки ($tag$ или $$)
                if char == '$':
                    # Проверяем следующий символ
                    if i + 1 < len(sql_content):
                        next_char = sql_content[i + 1]
                        if next_char == '$':
                            # Это $$ (безымянный dollar quote)
                            in_dollar_quote = True
                            dollar_tag = ''
                            i += 1
                            current_command.append('$')
                        elif next_char.isalnum() or next_char == '_':
                            # Это $tag$ - начинаем собирать тег
                            tag_start = i + 1
                            tag_end = tag_start
                            while tag_end < len(sql_content) and (sql_content[tag_end].isalnum() or sql_content[tag_end] == '_'):
                                tag_end += 1
                            if tag_end < len(sql_content) and sql_content[tag_end] == '$':
                                # Нашли закрывающий $ для тега
                                dollar_tag = sql_content[tag_start:tag_end]
                                in_dollar_quote = True
                                current_command.extend(sql_content[tag_start:tag_end + 1])
                                i = tag_end
                elif char == "'":
                    in_single_quote = True
                elif char == '"':
                    in_double_quote = True
                elif char == ';':
                    # Конец команды
                    command_text = ''.join(current_command).strip()
                    if command_text and not command_text.startswith('--'):
                        commands.append(command_text)
                    current_command = []
            else:
                if in_dollar_quote:
                    # Проверяем закрытие dollar quote
                    if char == '$':
                        if dollar_tag == '':
                            # Безымянный $$ - проверяем следующий символ
                            if i + 1 < len(sql_content) and sql_content[i + 1] == '$':
                                # Закрывающий $$
                                in_dollar_quote = False
                                dollar_tag = None
                                i += 1
                                current_command.append('$')
                        else:
                            # Именованный $tag$ - проверяем, совпадает ли тег
                            if i + len(dollar_tag) + 1 < len(sql_content):
                                potential_tag = sql_content[i + 1:i + 1 + len(dollar_tag)]
                                if potential_tag == dollar_tag and sql_content[i + 1 + len(dollar_tag)] == '$':
                                    # Закрывающий $tag$
                                    in_dollar_quote = False
                                    current_command.extend(dollar_tag + '$')
                                    i += len(dollar_tag) + 1
                                    dollar_tag = None
                                    continue
                elif in_single_quote and char == "'":
                    # Проверяем экранированную кавычку
                    if i + 1 < len(sql_content) and sql_content[i + 1] == "'":
                        # Двойная кавычка - экранирование, пропускаем
                        i += 1
                        current_command.append("'")
                        continue
                    in_single_quote = False
                elif in_double_quote and char == '"':
                    if i + 1 < len(sql_content) and sql_content[i + 1] == '"':
                        # Двойная кавычка - экранирование, пропускаем
                        i += 1
                        current_command.append('"')
                        continue
                    in_double_quote = False
            
            i += 1
        
        # Если осталась незавершённая команда
        if current_command:
            command_text = ''.join(current_command).strip()
            if command_text and not command_text.startswith('--'):
                commands.append(command_text)
        
        # Выполняем каждую команду
        for cmd in commands:
            cmd = cmd.strip()
            if cmd and not cmd.startswith('--'):
                # Удаляем завершающую точку с запятой
                if cmd.endswith(';'):
                    cmd = cmd[:-1].strip()
                if cmd:
                    await conn.execute(cmd)
        
        # Записываем версию в schema_migrations
        await conn.execute(
            "INSERT INTO schema_migrations (version) VALUES ($1) ON CONFLICT (version) DO NOTHING",
            version
        )
        
        logger.info(f"Migration {version} applied successfully")
        return True
        
    except Exception as e:
        logger.exception(f"Error applying migration {version}: {e}")
        raise


async def run_migrations(conn: asyncpg.Connection) -> bool:
    """
    Применить все неприменённые миграции
    
    Args:
        conn: Соединение с БД (должно быть вне транзакции, мы создадим свою)
        
    Returns:
        True если все миграции применены успешно, False если ошибка
    """
    try:
        # Создаём таблицу миграций
        await ensure_migrations_table(conn)
        
        # Получаем список применённых миграций
        applied = await get_applied_migrations(conn)
        logger.info(f"Applied migrations: {sorted(applied)}")
        
        # Получаем список файлов миграций
        migration_files = get_migration_files()
        
        if not migration_files:
            logger.warning("No migration files found")
            return True
        
        logger.info(f"Found {len(migration_files)} migration files")
        
        # Применяем каждую неприменённую миграцию в транзакции
        for version, migration_path in migration_files:
            if version in applied:
                logger.debug(f"Migration {version} already applied, skipping")
                continue
            
            # Применяем миграцию в транзакции
            # Каждая миграция выполняется в отдельной транзакции
            # Если миграция падает, она откатывается, но уже применённые остаются
            try:
                async with conn.transaction():
                    await apply_migration(conn, version, migration_path)
            except Exception as e:
                logger.exception(f"Failed to apply migration {version}: {e}")
                raise  # Пробрасываем исключение, чтобы остановить процесс миграций
        
        logger.info("All migrations applied successfully")
        return True
        
    except Exception as e:
        logger.exception(f"Error running migrations: {e}")
        return False


async def run_migrations_safe(pool: asyncpg.Pool) -> bool:
    """
    Безопасное применение миграций с использованием пула соединений
    
    Args:
        pool: Пул соединений с БД
        
    Returns:
        True если все миграции применены успешно, False если ошибка
    """
    async with pool.acquire() as conn:
        return await run_migrations(conn)

