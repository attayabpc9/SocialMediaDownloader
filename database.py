"""Database engine and session factory shared by web and worker services."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from models import Base


_engine_options = {'pool_pre_ping': True}
if DATABASE_URL.startswith('sqlite'):
    _engine_options['connect_args'] = {'check_same_thread': False}

engine = create_engine(DATABASE_URL, **_engine_options)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(bind=engine)
    columns = {column['name']
               for column in inspect(engine).get_columns('jobs')}
    additions = {
        'selected_format': 'VARCHAR(64)',
        'title': 'VARCHAR(500)',
        'thumbnail_url': 'TEXT',
        'available_formats': 'TEXT',
        'progress': 'INTEGER NOT NULL DEFAULT 0',
        'total_bytes': 'INTEGER',
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(
                    f'ALTER TABLE jobs ADD COLUMN {name} {definition}'
                ))
