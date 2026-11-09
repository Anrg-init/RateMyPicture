"""Tests for database URL handling that do not need PostgreSQL running."""

import os
import unittest
from unittest.mock import patch

from ratemypic.database import get_database_url


class DatabaseUrlTests(unittest.TestCase):
    def test_postgres_urls_use_asyncpg(self) -> None:
        urls = (
            "postgresql://user:password@localhost/rate_test",
            "postgresql+asyncpg://user:password@localhost/rate_test",
            "postgresql+psycopg://user:password@localhost/rate_test",
            "postgres://user:password@localhost/rate_test",
        )

        for database_url in urls:
            with self.subTest(database_url=database_url):
                with patch.dict(os.environ, {"TEST_DATABASE_URL": database_url}):
                    url = get_database_url()

                self.assertEqual(url.drivername, "postgresql+asyncpg")

    def test_non_postgres_url_is_rejected(self) -> None:
        with patch.dict(os.environ, {"TEST_DATABASE_URL": "sqlite:///local.db"}):
            with self.assertRaisesRegex(ValueError, "must be a PostgreSQL"):
                get_database_url()


if __name__ == "__main__":
    unittest.main()