from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "postgresql://std_user:std_secure_password@localhost:5439/std_archive_db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema():
    """Идемпотентная мини-миграция для уже существующих баз.

    `Base.metadata.create_all` не изменяет существующие таблицы, поэтому при
    обновлении приложения на старом томе данных добавляем недостающие колонки
    вручную. Для чистого тома схему создаёт `init.sql`.
    """
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE item ADD COLUMN IF NOT EXISTS designation TEXT"
        ))
        conn.execute(text(
            "ALTER TABLE item ADD COLUMN IF NOT EXISTS inventory_id INTEGER"
        ))

    # Уникальность инвентарного номера — отдельной транзакцией,
    # чтобы при وجودе дублей не откатились миграции выше.
    try:
        with engine.begin() as conn:
            conn.execute(text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'uq_item_inventory_id'
                          AND conrelid = 'item'::regclass
                    ) THEN
                        ALTER TABLE item
                            ADD CONSTRAINT uq_item_inventory_id UNIQUE (inventory_id);
                    END IF;
                END$$;
                """
            ))
    except Exception:
        pass  # Дубли уже есть — ограничение применится после очистки данных


def get_db():
    return SessionLocal()