import unittest

from mcp_server.sql import QueryValidationError, coerce_limit, is_fetch_sql, is_likely_write_sql, normalize_query


class SqlValidationTests(unittest.TestCase):
    def test_normalize_query_trims_semicolon(self):
        self.assertEqual(normalize_query(" SELECT 1; "), "SELECT 1")

    def test_normalize_query_rejects_multiple_statements(self):
        with self.assertRaises(QueryValidationError):
            normalize_query("SELECT 1; SELECT 2")

    def test_normalize_query_rejects_empty_input(self):
        with self.assertRaises(QueryValidationError):
            normalize_query("   ")

    def test_normalize_query_allows_semicolon_inside_string_literal(self):
        # Should NOT raise — the semicolon is inside a string literal, not a statement separator.
        result = normalize_query("SELECT 'a;b' AS val")
        self.assertEqual(result, "SELECT 'a;b' AS val")

    def test_normalize_query_rejects_semicolon_after_string_literal(self):
        with self.assertRaises(QueryValidationError):
            normalize_query("SELECT 'ok'; DROP TABLE users")

    def test_is_likely_write_sql(self):
        self.assertTrue(is_likely_write_sql("insert into demo values (1)"))
        self.assertTrue(is_likely_write_sql("  delete from demo"))
        self.assertFalse(is_likely_write_sql("select * from demo"))

    def test_is_fetch_sql(self):
        self.assertTrue(is_fetch_sql("select * from demo"))
        self.assertTrue(is_fetch_sql(" explain select 1"))
        self.assertFalse(is_fetch_sql("update demo set x = 1"))


class CoerceLimitTests(unittest.TestCase):
    def test_coerce_limit_returns_valid_value(self):
        self.assertEqual(coerce_limit(10, default=50), 10)

    def test_coerce_limit_uses_default_when_none(self):
        self.assertEqual(coerce_limit(None, default=50), 50)

    def test_coerce_limit_rejects_zero(self):
        with self.assertRaises(QueryValidationError):
            coerce_limit(0, default=50)

    def test_coerce_limit_rejects_over_maximum(self):
        with self.assertRaises(QueryValidationError):
            coerce_limit(201, default=50, maximum=200)
