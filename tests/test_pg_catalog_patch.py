"""
Unit tests for pg_catalog patching.

Tests verify that the PostgreSQL base module is correctly patched to use
Redshift's pg_catalog definitions, preventing duplicate table errors in
inherited methods like get_multi_table_comment().

Issue: sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DuplicateAlias)
       table name "pg_class" specified more than once
"""
import pytest
from sqlalchemy.engine.reflection import ObjectKind, ObjectScope

# IMPORTANT: Import the dialect FIRST to trigger the pg_catalog patching
# The patch happens at module import time (lines 37-42 in dialect.py)
from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2  # noqa: F401


class TestPgCatalogPatching:
    """Test suite for pg_catalog module patching."""

    def test_postgresql_base_uses_redshift_pg_catalog(self):
        """
        Test that PostgreSQL base module is patched with Redshift's pg_catalog.

        This is the core of the fix - ensuring all inherited PostgreSQL methods
        use Redshift's table definitions instead of PostgreSQL's.
        """
        import sqlalchemy.dialects.postgresql.base as pg_base
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog

        # Verify the patch worked
        assert pg_base.pg_catalog is rs_pg_catalog, \
            "PostgreSQL base should use Redshift's pg_catalog"

        # Verify it's actually Redshift's module, not PostgreSQL's
        assert 'sqlalchemy_redshift' in pg_base.pg_catalog.__name__, \
            "Should be sqlalchemy_redshift.pg_catalog"

    def test_pg_class_table_object_is_redshifts(self):
        """
        Test that pg_class table object is from Redshift's pg_catalog.

        This ensures queries won't have duplicate pg_class references.
        """
        import sqlalchemy.dialects.postgresql.base as pg_base
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog

        # The table objects should be identical (same object in memory)
        assert pg_base.pg_catalog.pg_class is rs_pg_catalog.pg_class, \
            "pg_class table objects should be identical"

    def test_pg_namespace_table_object_is_redshifts(self):
        """Test that pg_namespace table object is from Redshift's pg_catalog."""
        import sqlalchemy.dialects.postgresql.base as pg_base
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog

        assert pg_base.pg_catalog.pg_namespace is rs_pg_catalog.pg_namespace, \
            "pg_namespace table objects should be identical"

    def test_pg_description_table_object_is_redshifts(self):
        """Test that pg_description table object is from Redshift's pg_catalog."""
        import sqlalchemy.dialects.postgresql.base as pg_base
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog

        assert pg_base.pg_catalog.pg_description is rs_pg_catalog.pg_description, \
            "pg_description table objects should be identical"

    def test_redshift_specific_columns_present(self):
        """
        Test that Redshift-specific columns are present in pg_class.

        Redshift's pg_class has columns like reldiststyle that don't exist
        in PostgreSQL's pg_class.
        """
        import sqlalchemy.dialects.postgresql.base as pg_base

        # Redshift-specific column
        assert hasattr(pg_base.pg_catalog.pg_class.c, 'reldiststyle'), \
            "Should have Redshift-specific column reldiststyle"

    def test_postgresql_only_columns_absent(self):
        """
        Test that PostgreSQL-only columns are NOT present in pg_class.

        PostgreSQL's pg_class has relpersistence which doesn't exist in Redshift.
        This column being absent is what necessitates the _pg_class_filter_scope_schema
        override.
        """
        import sqlalchemy.dialects.postgresql.base as pg_base

        # PostgreSQL-only column should not be present
        assert not hasattr(pg_base.pg_catalog.pg_class.c, 'relpersistence'), \
            "Should NOT have PostgreSQL-only column relpersistence"


class TestCommentQueryInheritance:
    """Test that inherited _comment_query method uses Redshift's tables."""

    def test_comment_query_uses_redshift_pg_class(self):
        """
        Test that _comment_query (inherited from PostgreSQL) uses Redshift's pg_class.

        This is the key test - it verifies the fix for the duplicate table error.
        """
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog

        dialect = RedshiftDialect_psycopg2()

        # Call the inherited _comment_query method
        query = dialect._comment_query(None, False, ObjectScope.DEFAULT, ObjectKind.TABLE)

        # Navigate the nested join structure to find pg_class
        # Structure is: ((pg_class LEFT JOIN pg_description) JOIN pg_namespace)
        from_objs = list(query.get_final_froms())
        assert len(from_objs) == 1, "Should have one FROM object (a nested join)"

        join_obj = from_objs[0]
        assert hasattr(join_obj, 'left'), "Should be a join with left side"
        assert hasattr(join_obj.left, 'left'), "Should have nested join"

        # The innermost left should be pg_class
        pg_class_in_query = join_obj.left.left

        # This is THE critical assertion - pg_class should be Redshift's
        assert pg_class_in_query is rs_pg_catalog.pg_class, \
            "Query should use Redshift's pg_class, not PostgreSQL's"

    def test_comment_query_uses_redshift_pg_description(self):
        """Test that _comment_query uses Redshift's pg_description."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog

        dialect = RedshiftDialect_psycopg2()
        query = dialect._comment_query(None, False, ObjectScope.DEFAULT, ObjectKind.TABLE)

        # Navigate to pg_description
        from_objs = list(query.get_final_froms())
        join_obj = from_objs[0]
        pg_description_in_query = join_obj.left.right

        assert pg_description_in_query is rs_pg_catalog.pg_description

    def test_comment_query_uses_redshift_pg_namespace(self):
        """Test that _comment_query uses Redshift's pg_namespace."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog

        dialect = RedshiftDialect_psycopg2()
        query = dialect._comment_query(None, False, ObjectScope.DEFAULT, ObjectKind.TABLE)

        # Navigate to pg_namespace
        from_objs = list(query.get_final_froms())
        join_obj = from_objs[0]
        pg_namespace_in_query = join_obj.right

        assert pg_namespace_in_query is rs_pg_catalog.pg_namespace


class TestSQLGeneration:
    """Test that generated SQL has no duplicate table references."""

    def test_no_duplicate_pg_class_in_from_clause(self):
        """
        Test that generated SQL doesn't have duplicate pg_class in FROM clause.

        This is the symptom that Redshift was rejecting - this test ensures
        it's fixed.
        """
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2

        dialect = RedshiftDialect_psycopg2()
        query = dialect._comment_query(None, False, ObjectScope.DEFAULT, ObjectKind.TABLE)

        # Compile to SQL
        compiled = query.compile(dialect=dialect)
        sql = str(compiled)

        # Count occurrences of "FROM pg_catalog.pg_class"
        # (should be exactly 1)
        from_clause = sql.split('WHERE')[0] if 'WHERE' in sql else sql
        pg_class_count = from_clause.count('FROM pg_catalog.pg_class')

        assert pg_class_count == 1, \
            f"Expected 1 'FROM pg_catalog.pg_class', found {pg_class_count}"

    def test_sql_contains_expected_joins(self):
        """Test that generated SQL has the expected JOIN structure."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2

        dialect = RedshiftDialect_psycopg2()
        query = dialect._comment_query(None, False, ObjectScope.DEFAULT, ObjectKind.TABLE)

        sql = str(query.compile(dialect=dialect))

        # Should have LEFT OUTER JOIN for pg_description
        assert 'LEFT OUTER JOIN pg_catalog.pg_description' in sql

        # Should have regular JOIN for pg_namespace
        assert 'JOIN pg_catalog.pg_namespace' in sql

        # Should have pg_class in SELECT
        assert 'pg_catalog.pg_class.relname' in sql

    @pytest.mark.parametrize('schema', [None, 'public', 'my_schema'])
    def test_sql_generation_with_different_schemas(self, schema):
        """Test SQL generation with different schema parameters."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2

        dialect = RedshiftDialect_psycopg2()
        query = dialect._comment_query(schema, False, ObjectScope.DEFAULT, ObjectKind.TABLE)

        # Should compile without errors
        sql = str(query.compile(dialect=dialect))

        # Should have only one FROM pg_catalog.pg_class
        from_clause = sql.split('WHERE')[0] if 'WHERE' in sql else sql
        pg_class_count = from_clause.count('FROM pg_catalog.pg_class')
        assert pg_class_count == 1

    @pytest.mark.parametrize('kind', [ObjectKind.TABLE, ObjectKind.VIEW])
    def test_sql_generation_with_different_kinds(self, kind):
        """Test SQL generation with different object kinds."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2

        dialect = RedshiftDialect_psycopg2()
        query = dialect._comment_query(None, False, ObjectScope.DEFAULT, kind)

        # Should compile without errors
        sql = str(query.compile(dialect=dialect))

        # Should have only one FROM pg_catalog.pg_class
        from_clause = sql.split('WHERE')[0] if 'WHERE' in sql else sql
        pg_class_count = from_clause.count('FROM pg_catalog.pg_class')
        assert pg_class_count == 1


class TestPgClassFilterScopeSchema:
    """Test the _pg_class_filter_scope_schema method."""

    def test_defaults_to_redshift_pg_class(self):
        """Test that method defaults to Redshift's pg_class when pg_class_table=None."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog
        from sqlalchemy import select

        dialect = RedshiftDialect_psycopg2()

        # Create a simple query
        query = select(rs_pg_catalog.pg_class.c.relname).select_from(
            rs_pg_catalog.pg_class
        )

        # Apply filter with pg_class_table=None
        filtered_query = dialect._pg_class_filter_scope_schema(
            query, None, None, None
        )

        # Should compile without errors
        sql = str(filtered_query.compile(dialect=dialect))

        # Should have pg_namespace joined
        assert 'pg_catalog.pg_namespace' in sql

    def test_uses_provided_pg_class_table(self):
        """Test that method uses provided pg_class_table parameter."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog
        from sqlalchemy import select

        dialect = RedshiftDialect_psycopg2()

        # Create a simple query
        query = select(rs_pg_catalog.pg_class.c.relname).select_from(
            rs_pg_catalog.pg_class
        )

        # Apply filter with explicit pg_class_table
        filtered_query = dialect._pg_class_filter_scope_schema(
            query, None, None, rs_pg_catalog.pg_class
        )

        # Should compile without errors
        sql = str(filtered_query.compile(dialect=dialect))

        # Should have pg_namespace joined
        assert 'pg_catalog.pg_namespace' in sql

    def test_schema_filter_applied(self):
        """Test that schema filter is correctly applied."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog
        from sqlalchemy import select

        dialect = RedshiftDialect_psycopg2()

        query = select(rs_pg_catalog.pg_class.c.relname).select_from(
            rs_pg_catalog.pg_class
        )

        # Apply filter with explicit schema
        filtered_query = dialect._pg_class_filter_scope_schema(
            query, 'public', None, None
        )

        sql = str(filtered_query.compile(dialect=dialect))

        # Should have schema filter in WHERE clause
        assert 'nspname' in sql


class TestMultipleDialectInstances:
    """Test that multiple dialect instances work correctly with patching."""

    def test_multiple_psycopg2_instances(self):
        """Test that multiple psycopg2 dialect instances work correctly."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog

        dialect1 = RedshiftDialect_psycopg2()
        dialect2 = RedshiftDialect_psycopg2()

        # Both should use the same patched pg_catalog
        query1 = dialect1._comment_query(None, False, ObjectScope.DEFAULT, ObjectKind.TABLE)
        query2 = dialect2._comment_query(None, False, ObjectScope.DEFAULT, ObjectKind.TABLE)

        from_objs1 = list(query1.get_final_froms())
        from_objs2 = list(query2.get_final_froms())

        pg_class1 = from_objs1[0].left.left
        pg_class2 = from_objs2[0].left.left

        # Both should be using the same Redshift pg_class object
        assert pg_class1 is rs_pg_catalog.pg_class
        assert pg_class2 is rs_pg_catalog.pg_class
        assert pg_class1 is pg_class2

    def test_different_dialect_types(self):
        """Test that different Redshift dialect types all use patched pg_catalog."""
        from sqlalchemy_redshift.dialect import (
            RedshiftDialect_psycopg2,
            RedshiftDialect_psycopg2cffi,
            RedshiftDialect_redshift_connector
        )
        from sqlalchemy_redshift import pg_catalog as rs_pg_catalog

        dialect_psycopg2 = RedshiftDialect_psycopg2()
        dialect_cffi = RedshiftDialect_psycopg2cffi()
        dialect_connector = RedshiftDialect_redshift_connector()

        # All should have access to the patched pg_catalog
        for dialect in [dialect_psycopg2, dialect_cffi, dialect_connector]:
            query = dialect._comment_query(None, False, ObjectScope.DEFAULT, ObjectKind.TABLE)
            from_objs = list(query.get_final_froms())
            pg_class = from_objs[0].left.left

            assert pg_class is rs_pg_catalog.pg_class, \
                f"{dialect.__class__.__name__} should use Redshift's pg_class"


class TestBackwardCompatibility:
    """Test that the patch doesn't break existing functionality."""

    def test_dialect_has_required_methods(self):
        """Test that dialect still has all required reflection methods."""
        from sqlalchemy_redshift.dialect import RedshiftDialect_psycopg2

        dialect = RedshiftDialect_psycopg2()

        # Methods that should exist
        required_methods = [
            'get_columns',
            'get_table_names',
            'get_view_names',
            'get_pk_constraint',
            'get_foreign_keys',
            'get_indexes',
            'get_unique_constraints',
            'get_check_constraints',
            'get_table_comment',
            'get_multi_table_comment',
            '_comment_query',
            '_pg_class_filter_scope_schema',
        ]

        for method_name in required_methods:
            assert hasattr(dialect, method_name), \
                f"Dialect should have method {method_name}"

    def test_pg_catalog_functions_available(self):
        """Test that pg_catalog functions are still available."""
        import sqlalchemy.dialects.postgresql.base as pg_base

        # Common functions that should be available
        assert hasattr(pg_base.pg_catalog, 'pg_table_is_visible')
        assert hasattr(pg_base.pg_catalog, 'format_type')
        assert hasattr(pg_base.pg_catalog, 'pg_get_viewdef')
        assert hasattr(pg_base.pg_catalog, 'pg_get_expr')
