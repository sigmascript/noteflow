from sqlalchemy import inspect

from .database import DATABASE_PATH, configure_database, create_tables, Model


def main() -> None:
    database = configure_database()
    try:
        expected = set(Model.metadata.tables)
        before = set(inspect(database.engine).get_table_names())
        create_tables(database)
        after = set(inspect(database.engine).get_table_names())
    finally:
        database.dispose()

    created = sorted((after - before) & expected)
    if created:
        print(f"NoteFlow tables created: {', '.join(created)} ({DATABASE_PATH})")
    else:
        print(f"NoteFlow database already initialized; no tables overwritten: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
