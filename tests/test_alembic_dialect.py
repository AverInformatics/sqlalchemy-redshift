from alembic.ddl.base import RenameTable, ColumnComment
from alembic.ddl.postgresql import PostgresqlColumnType
from alembic import migration
from sqlalchemy import Integer, VARCHAR
import warnings

from sqlalchemy_redshift import dialect


def test_configure_migration_context():
    context = migration.MigrationContext.configure(
        url='redshift+psycopg2://mydb'
    )
    assert isinstance(context.impl, dialect.RedshiftImpl)


def test_rename_table(stub_redshift_dialect):
    compiler = dialect.RedshiftDDLCompiler(stub_redshift_dialect, None)
    sql = compiler.process(RenameTable("old", "new", "schema"))
    assert sql == 'ALTER TABLE schema."old" RENAME TO "new"'


def test_alter_column_comment(stub_redshift_dialect):
    compiler = dialect.RedshiftDDLCompiler(stub_redshift_dialect, None)
    sql = compiler.process(
        ColumnComment("table_name", "column_name", "my comment")
    )
    assert sql == "COMMENT ON COLUMN table_name.column_name IS 'my comment'"


def test_alter_column_type_varchar_supported(stub_redshift_dialect):
    """Test VARCHAR size change - supported by Redshift"""
    compiler = dialect.RedshiftDDLCompiler(stub_redshift_dialect, None)
    sql = compiler.process(
        PostgresqlColumnType("table_name", "column_name", VARCHAR(100))
    )
    assert sql == 'ALTER TABLE table_name ALTER COLUMN column_name TYPE VARCHAR(100)'


def test_alter_column_type_unsupported_warns(stub_redshift_dialect):
    """Test non-VARCHAR type change - unsupported by Redshift, should warn"""
    compiler = dialect.RedshiftDDLCompiler(stub_redshift_dialect, None)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        sql = compiler.process(
            PostgresqlColumnType("table_name", "column_name", Integer())
        )

        # Should generate a warning
        assert len(w) == 1
        assert "Redshift does not support ALTER COLUMN TYPE" in str(w[0].message)
        assert "manual migration" in str(w[0].message)

        # Should still generate SQL (for documentation purposes)
        assert 'ALTER TABLE table_name' in sql
        assert 'column_name' in sql
