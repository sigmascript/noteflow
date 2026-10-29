"""Explicit initialization for a disposable NoteFlow AuroraSQL database."""

from .database import DATABASE_PATH, configure_database, create_tables


def main():
    with configure_database() as database:
        create_tables(database)
    print(f"NoteFlow tables created: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
