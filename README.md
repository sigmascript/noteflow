# NoteFlow

**NoteFlow** Is a small, independent notes application built with [Aurora MVC](https://github.com/sigmascript/aurora-mvc). It demonstrates authentication, server-rendered views, SQLite-backed models, sessions, CSRF protection, and per-user note ownership.

NoteFlow is a **GitHub-only reference application**, not part of the Aurora MVC framework package. It is **not published to PyPI**; the local `pyproject.toml` simply makes dependency installation convenient.

## Requirements

- A Python version supported by Aurora MVC `1.0.0a1` (Python 3.14 is used in the team's verified environment)
- Git (to clone the repository)

## Get started

```bash
git clone https://github.com/sigmascript/noteflow.git
cd noteflow

# Windows: create the environment with the Python launcher
py -3.14 -m venv .venv
source .venv/Scripts/activate  # Git Bash

python -m pip install -e .
python -m noteflow.init_db
aurora run noteflow.app:app
```

On Linux or macOS, create the environment with a supported `python3` executable and activate it using `source .venv/bin/activate` instead.

Open <http://127.0.0.1:8000> and create an account to start using NoteFlow.

**Important:** `aurora db init` is not available in Aurora MVC `1.0.0a1`. The `python -m noteflow.init_db` command is NoteFlow's current application-specific initializer. It creates missing tables but does **not** migrate existing schemas.

## How the application is created

NoteFlow uses an **application factory**, `create_app()`, defined in `noteflow/app.py`. This is a normal Python function that creates and returns an Aurora ASGI application; it is not a separate command or a database initializer.

When called, `create_app(session_database_path=..., secure=...)`:

1. Constructs `Aurora(...)` with NoteFlow's view directories, shared template context, `Cache-Control: no-store` view headers, and session configuration.
2. Registers the home page, authentication routes, and notes routes. Controller classes handle their corresponding HTTP methods.
3. Returns the configured application object without creating or migrating the notes database tables.

At the bottom of `noteflow/app.py`, the module binds the default notes database with `configure_database()` and creates a local-development ASGI instance named `app` with `secure=False`. The command `aurora run noteflow.app:app` tells Aurora to import that module and serve the `app` object. Importing the module therefore has a database-binding side effect; it does not initialize the notes tables.

**Why use a factory?** It separates application setup from the server entry point and lets integration tests call `create_app()` with their own temporary session database. The tests also call `configure_database()` with a temporary notes database before constructing the test app, so they do not operate on the real NoteFlow SQLite files.

The `secure=False` option is for localhost HTTP only. Use HTTPS and secure session cookies for an actual deployment; this sample does not provide a production deployment recipe.

## Features

- Sign up, sign in, and sign out
- Create, read, update, and delete personal notes
- Account-specific note access controls
- Session authentication and CSRF-protected forms
- SQLite persistence and server-rendered HTML

## Run tests

From the activated virtual environment:

```bash
python -m unittest discover -s tests -v
```

The integration tests create temporary SQLite databases and use independent simulated browser sessions.

## Development and deployment notes

The default `noteflow.app:app` entry point is configured for **local HTTP development** and uses `secure=False` for its session cookie settings. This is **not a production-ready HTTPS deployment configuration**. For deployment, configure secure cookies, HTTPS, and an appropriate production ASGI server setup.

The default local application stores its database and session database inside the `noteflow/` package directory. These files are intentionally excluded from Git. Do not commit real account data or SQLite sidecar files.

## Framework development

If you are contributing to Aurora MVC itself, its own repository uses a separate editable development installation:

```bash
python -m pip install -e ".[dev]"
```

That command is for the **Aurora MVC source checkout**, not for installing NoteFlow.

## License

MIT. See [LICENSE](LICENSE).
