# RateMyPic

Posts can contain one, two, or three photos. The bot stores Telegram photo IDs,
not image bytes. Apply database changes with `uv run alembic upgrade head`.

## Bot commands

- `/start` opens the main menu for an existing account or starts registration.
- `/terms` displays the current Terms of Service.
- `/cancel` stops the current action and returns registered users to the main menu.
- `/edit` opens profile and post editing, including confirmed account or post deletion.

## PostgreSQL setup

Put your PostgreSQL connection address in the project's `.env` file:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/ratemypic
```

Keep the real password private. The connection helper automatically selects the
installed `psycopg` driver.

The database helper uses async SQLAlchemy and `asyncpg`. To check the connection,
run this from the project folder:

```bash
uv run python -c "import asyncio; from ratemypic.database import test_connection; asyncio.run(test_connection())"
```

For local development, create the tables and indexes from `models.py` with:

```bash
uv run python -c "import asyncio; from ratemypic.database import create_tables; asyncio.run(create_tables())"
```

Use `session_scope()` with `async with` in bot handlers. It commits when the
block succeeds and rolls back if an error occurs. Call `close_database()` when
the bot shuts down so pooled connections are closed cleanly. The `updated_at`
columns are updated when their row is changed through SQLAlchemy.

PostgreSQL also prevents a user with `status='banned'` from being unbanned.
For schema changes on the database, run the Alembic migration:

```bash
uv run alembic upgrade head
```

Use Alembic for deployed schema changes instead of `create_tables()`. The
initial migration is in `migrations/versions/0001_initial_schema.py`.

Example database use inside an async bot handler:

```python
from ratemypic.database import session_scope

async with session_scope() as session:
	# Run async SQLAlchemy queries with this session.
	...
```

Run the local tests with `uv run python -m unittest discover -s tests`.
