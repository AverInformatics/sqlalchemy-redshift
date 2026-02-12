"""
Redshift-compatible pg_catalog system table definitions.

This module provides SQLAlchemy Table definitions for Redshift's pg_catalog
system tables, similar to SQLAlchemy's postgresql.pg_catalog module but
adapted for Redshift's limitations.

Key differences from PostgreSQL:
- Redshift is based on PostgreSQL 8.0.2 with some later features backported
- Many columns introduced in PostgreSQL 9.x+ are not available
- Some tables (pg_sequence, pg_inherits) don't exist in Redshift
- Redshift has additional system views (svv_*, stv_*, etc.)

See: https://docs.aws.amazon.com/redshift/latest/dg/c_intro_catalog.html
"""

from __future__ import annotations

from typing import Any
from typing import Optional
from typing import Sequence
from typing import TYPE_CHECKING

from sqlalchemy import Column
from sqlalchemy import func
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy.types import BigInteger
from sqlalchemy.types import Boolean
from sqlalchemy.types import CHAR
from sqlalchemy.types import Float
from sqlalchemy.types import Integer
from sqlalchemy.types import SmallInteger
from sqlalchemy.types import String
from sqlalchemy.types import Text
from sqlalchemy.types import TypeDecorator

# Import PostgreSQL-specific types
try:
    from sqlalchemy.dialects.postgresql.array import ARRAY
    from sqlalchemy.dialects.postgresql.types import OID
    from sqlalchemy.dialects.postgresql.types import REGCLASS
except ImportError:
    # Fallback for older SQLAlchemy versions
    from sqlalchemy.dialects.postgresql import ARRAY, OID, REGCLASS

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect
    from sqlalchemy.sql.type_api import _ResultProcessorType


# Custom types for pg_catalog
class NAME(TypeDecorator):
    """
    PostgreSQL NAME type - identifier name (64 bytes max).
    Redshift supports this type.
    """
    impl = String(64)
    cache_ok = True


class PG_NODE_TREE(TypeDecorator):
    """
    PostgreSQL pg_node_tree type - internal representation of parsed SQL.
    Redshift supports this type for view definitions and defaults.
    """
    impl = Text
    cache_ok = True


class INT2VECTOR(TypeDecorator):
    """
    PostgreSQL int2vector type - array of smallint values.
    Used for index keys and constraint keys.
    """
    impl = ARRAY(SmallInteger)
    cache_ok = True


class OIDVECTOR(TypeDecorator):
    """
    PostgreSQL oidvector type - array of OID values.
    Used for index collations and operator classes.
    """
    impl = ARRAY(OID)
    cache_ok = True


class _SpaceVector:
    """
    Base class for vector types that are stored as space-separated strings.
    Redshift sometimes returns vectors as space-separated strings.
    """
    def result_processor(
        self, dialect: Dialect, coltype: object
    ) -> _ResultProcessorType[list[int]]:
        def process(value: Any) -> Optional[list[int]]:
            if value is None:
                return value
            return [int(p) for p in value.split(" ")]
        return process


# REGPROC is an alias for REGCLASS in Redshift
REGPROC = REGCLASS


# PostgreSQL catalog functions available in Redshift
_pg_cat = func.pg_catalog
quote_ident = _pg_cat.quote_ident
pg_table_is_visible = _pg_cat.pg_table_is_visible
pg_type_is_visible = _pg_cat.pg_type_is_visible
pg_get_viewdef = _pg_cat.pg_get_viewdef
format_type = _pg_cat.format_type
pg_get_expr = _pg_cat.pg_get_expr
pg_get_constraintdef = _pg_cat.pg_get_constraintdef

# Note: pg_get_indexdef and pg_get_serial_sequence exist but may have
# limited functionality in Redshift compared to PostgreSQL


# Redshift relation kind constants
# Based on pg_class.relkind values
RELKINDS_TABLE = ("r",)  # Regular table
RELKINDS_VIEW = ("v",)  # View
RELKINDS_MAT_VIEW = ("m",)  # Materialized view (supported in Redshift)
RELKINDS_EXTERNAL = ("f",)  # Foreign/External table (Redshift Spectrum)
RELKINDS_SEQUENCE = ("S",)  # Sequence
RELKINDS_PARTITIONED = ("p",)  # Partitioned table (limited support)

# Combined constants for convenience
RELKINDS_TABLE_NO_FOREIGN = ("r", "p")
RELKINDS_TABLE_WITH_FOREIGN = ("r", "p", "f")
RELKINDS_ALL_TABLE_LIKE = ("r", "v", "m", "f", "p")


# Metadata container for pg_catalog tables
pg_catalog_meta = MetaData(schema="pg_catalog")


# pg_namespace - Schema information
pg_namespace = Table(
    "pg_namespace",
    pg_catalog_meta,
    Column("oid", OID),
    Column("nspname", NAME),
    Column("nspowner", OID),
)


# pg_class - Table/view/index information
# NOTE: This is a critical table. Redshift is missing several columns
# that exist in PostgreSQL, most notably relpersistence.
pg_class = Table(
    "pg_class",
    pg_catalog_meta,
    Column("oid", OID),
    Column("relname", NAME),
    Column("relnamespace", OID),
    Column("reltype", OID),
    Column("reloftype", OID),
    Column("relowner", OID),
    Column("relam", OID),
    Column("relfilenode", OID),
    Column("reltablespace", OID),
    Column("relpages", Integer),
    Column("reltuples", Float),
    # Column("relallvisible", Integer),  # NOT in Redshift
    Column("reltoastrelid", OID),
    Column("relhasindex", Boolean),
    Column("relisshared", Boolean),
    # Column("relpersistence", CHAR),  # NOT in Redshift - causes errors!
    Column("relkind", CHAR),
    Column("relnatts", SmallInteger),
    Column("relchecks", SmallInteger),
    Column("relhasrules", Boolean),
    Column("relhastriggers", Boolean),
    Column("relhassubclass", Boolean),
    # Column("relrowsecurity", Boolean),  # NOT in Redshift
    # Column("relforcerowsecurity", Boolean),  # NOT in Redshift
    # Column("relispopulated", Boolean),  # NOT in Redshift
    # Column("relreplident", CHAR),  # NOT in Redshift
    # Column("relispartition", Boolean),  # NOT in Redshift
    # Column("relrewrite", OID),  # NOT in Redshift
    Column("reldiststyle", SmallInteger),  # Redshift-specific: 0=EVEN, 1=KEY, 8=ALL
    Column("reloptions", ARRAY(Text)),
    Column("relacl", ARRAY(Text)),
)


# pg_type - Data type information
pg_type = Table(
    "pg_type",
    pg_catalog_meta,
    Column("oid", OID),
    Column("typname", NAME),
    Column("typnamespace", OID),
    Column("typowner", OID),
    Column("typlen", SmallInteger),
    Column("typbyval", Boolean),
    Column("typtype", CHAR),
    Column("typcategory", CHAR),
    Column("typispreferred", Boolean),
    Column("typisdefined", Boolean),
    Column("typdelim", CHAR),
    Column("typrelid", OID),
    Column("typelem", OID),
    Column("typarray", OID),
    Column("typinput", REGPROC),
    Column("typoutput", REGPROC),
    Column("typreceive", REGPROC),
    Column("typsend", REGPROC),
    Column("typmodin", REGPROC),
    Column("typmodout", REGPROC),
    Column("typanalyze", REGPROC),
    Column("typalign", CHAR),
    Column("typstorage", CHAR),
    Column("typnotnull", Boolean),
    Column("typbasetype", OID),
    Column("typtypmod", Integer),
    Column("typndims", Integer),
    Column("typcollation", OID),
    Column("typdefault", Text),
)


# pg_index - Index information
# NOTE: Redshift doesn't support traditional indexes, but this table
# is used for primary key and unique constraint metadata.
pg_index = Table(
    "pg_index",
    pg_catalog_meta,
    Column("indexrelid", OID),
    Column("indrelid", OID),
    Column("indnatts", SmallInteger),
    # Column("indnkeyatts", SmallInteger),  # NOT in Redshift (PG 11+)
    Column("indisunique", Boolean),
    # Column("indnullsnotdistinct", Boolean),  # NOT in Redshift (PG 15+)
    Column("indisprimary", Boolean),
    # Column("indisexclusion", Boolean),  # NOT in Redshift
    Column("indimmediate", Boolean),
    Column("indisclustered", Boolean),
    Column("indisvalid", Boolean),
    Column("indcheckxmin", Boolean),
    Column("indisready", Boolean),
    # Column("indislive", Boolean),  # NOT in Redshift
    Column("indisreplident", Boolean),
    Column("indkey", INT2VECTOR),
    Column("indcollation", OIDVECTOR),
    Column("indclass", OIDVECTOR),
    Column("indoption", INT2VECTOR),
    Column("indexprs", PG_NODE_TREE),
    Column("indpred", PG_NODE_TREE),
)


# pg_attribute - Column information
pg_attribute = Table(
    "pg_attribute",
    pg_catalog_meta,
    Column("attrelid", OID),
    Column("attname", NAME),
    Column("atttypid", OID),
    Column("attstattarget", Integer),
    Column("attlen", SmallInteger),
    Column("attnum", SmallInteger),
    Column("attndims", Integer),
    Column("attcacheoff", Integer),
    Column("atttypmod", Integer),
    Column("attbyval", Boolean),
    Column("attstorage", CHAR),
    Column("attalign", CHAR),
    Column("attnotnull", Boolean),
    Column("atthasdef", Boolean),
    # Column("atthasmissing", Boolean),  # NOT in Redshift (PG 11+)
    # Column("attidentity", CHAR),  # NOT in Redshift (PG 10+)
    # Column("attgenerated", CHAR),  # NOT in Redshift (PG 12+)
    Column("attisdropped", Boolean),
    Column("attislocal", Boolean),
    Column("attinhcount", Integer),
    Column("attcollation", OID),
    # Redshift-specific columns
    Column("attencodingtype", Integer),  # Redshift compression encoding
    Column("attsortkeyord", Integer),  # Redshift sort key order
    Column("attisdistkey", Boolean),  # Redshift distribution key
)


# pg_constraint - Constraint information
pg_constraint = Table(
    "pg_constraint",
    pg_catalog_meta,
    Column("oid", OID),
    Column("conname", NAME),
    Column("connamespace", OID),
    Column("contype", CHAR),  # p=primary, f=foreign, u=unique, c=check
    Column("condeferrable", Boolean),
    Column("condeferred", Boolean),
    Column("convalidated", Boolean),
    Column("conrelid", OID),
    Column("contypid", OID),
    Column("conindid", OID),
    # Column("conparentid", OID),  # NOT in Redshift (PG 11+)
    Column("confrelid", OID),
    Column("confupdtype", CHAR),
    Column("confdeltype", CHAR),
    Column("confmatchtype", CHAR),
    Column("conislocal", Boolean),
    Column("coninhcount", Integer),
    # Column("connoinherit", Boolean),  # NOT in Redshift (PG 9.2+)
    Column("conkey", ARRAY(SmallInteger)),
    Column("confkey", ARRAY(SmallInteger)),
)


# pg_attrdef - Column default values
pg_attrdef = Table(
    "pg_attrdef",
    pg_catalog_meta,
    Column("oid", OID),
    Column("adrelid", OID),
    Column("adnum", SmallInteger),
    Column("adbin", PG_NODE_TREE),
)


# pg_description - Comments on database objects
pg_description = Table(
    "pg_description",
    pg_catalog_meta,
    Column("objoid", OID),
    Column("classoid", OID),
    Column("objsubid", Integer),
    Column("description", Text),
)


# pg_enum - Enum type values
pg_enum = Table(
    "pg_enum",
    pg_catalog_meta,
    Column("oid", OID),
    Column("enumtypid", OID),
    Column("enumsortorder", Float()),
    Column("enumlabel", NAME),
)


# pg_am - Access method information
pg_am = Table(
    "pg_am",
    pg_catalog_meta,
    Column("oid", OID),
    Column("amname", NAME),
    # Column("amhandler", REGPROC),  # NOT in Redshift (PG 9.6+)
    # Column("amtype", CHAR),  # NOT in Redshift (PG 9.6+)
)


# pg_collation - Collation information
pg_collation = Table(
    "pg_collation",
    pg_catalog_meta,
    Column("oid", OID),
    Column("collname", NAME),
    Column("collnamespace", OID),
    Column("collowner", OID),
    # Column("collprovider", CHAR),  # NOT in Redshift (PG 10+)
    # Column("collisdeterministic", Boolean),  # NOT in Redshift (PG 12+)
    Column("collencoding", Integer),
    Column("collcollate", Text),
    Column("collctype", Text),
    # Column("colliculocale", Text),  # NOT in Redshift
    # Column("collicurules", Text),  # NOT in Redshift (PG 16+)
    # Column("collversion", Text),  # NOT in Redshift (PG 10+)
)


# pg_opclass - Operator class information
pg_opclass = Table(
    "pg_opclass",
    pg_catalog_meta,
    Column("oid", OID),
    Column("opcmethod", OID),
    Column("opcname", NAME),
    Column("opcnamespace", OID),
    Column("opcowner", OID),
    Column("opcfamily", OID),
    Column("opcintype", OID),
    Column("opcdefault", Boolean),
    Column("opckeytype", OID),
)


# pg_tablespace - Tablespace information
pg_tablespace = Table(
    "pg_tablespace",
    pg_catalog_meta,
    Column("oid", OID),
    Column("spcname", NAME),
    Column("spcowner", OID),
    Column("spclocation", Text),
    Column("spcacl", ARRAY(Text)),
)


# pg_user - User information (this is actually a view in PostgreSQL/Redshift)
pg_user = Table(
    "pg_user",
    pg_catalog_meta,
    Column("usename", NAME),
    Column("usesysid", OID),
    Column("usecreatedb", Boolean),
    Column("usesuper", Boolean),
    Column("usecatupd", Boolean),
    Column("passwd", Text),
    Column("valuntil", Text),
    Column("useconfig", ARRAY(Text)),
)


# Note: The following tables don't exist in Redshift:
# - pg_sequence (Redshift uses a different sequence mechanism)
# - pg_inherits (Redshift doesn't support table inheritance)
# - pg_partitioned_table (Redshift has limited partitioning support)


# Redshift-specific system views (selected commonly used ones)
# These are not part of standard pg_catalog but are useful for Redshift

# svv_external_tables - External tables (Redshift Spectrum)
svv_external_tables = Table(
    "svv_external_tables",
    MetaData(schema="pg_catalog"),  # Actually in public but accessed via pg_catalog
    Column("schemaname", NAME),
    Column("tablename", NAME),
    Column("location", Text),
    Column("input_format", Text),
    Column("output_format", Text),
    Column("serialization_lib", Text),
    Column("serde_parameters", Text),
    Column("compressed", Integer),
    Column("parameters", Text),
)


# svv_external_columns - External table columns
svv_external_columns = Table(
    "svv_external_columns",
    MetaData(schema="pg_catalog"),
    Column("schemaname", NAME),
    Column("tablename", NAME),
    Column("columnname", NAME),
    Column("external_type", Text),
    Column("columnnum", Integer),
    Column("part_key", Integer),
)


# svv_external_schemas - External schemas
svv_external_schemas = Table(
    "svv_external_schemas",
    MetaData(schema="pg_catalog"),
    Column("esoid", OID),
    Column("eskind", Integer),
    Column("schemaname", NAME),
    Column("esowner", OID),
    Column("databasename", NAME),
    Column("esoptions", Text),
)


__all__ = [
    # Types
    "NAME",
    "PG_NODE_TREE",
    "INT2VECTOR",
    "OIDVECTOR",
    "REGPROC",
    # Functions
    "quote_ident",
    "pg_table_is_visible",
    "pg_type_is_visible",
    "pg_get_viewdef",
    "format_type",
    "pg_get_expr",
    "pg_get_constraintdef",
    # Constants
    "RELKINDS_TABLE",
    "RELKINDS_VIEW",
    "RELKINDS_MAT_VIEW",
    "RELKINDS_EXTERNAL",
    "RELKINDS_SEQUENCE",
    "RELKINDS_PARTITIONED",
    "RELKINDS_TABLE_NO_FOREIGN",
    "RELKINDS_TABLE_WITH_FOREIGN",
    "RELKINDS_ALL_TABLE_LIKE",
    # Metadata
    "pg_catalog_meta",
    # Tables
    "pg_namespace",
    "pg_class",
    "pg_type",
    "pg_index",
    "pg_attribute",
    "pg_constraint",
    "pg_attrdef",
    "pg_description",
    "pg_enum",
    "pg_am",
    "pg_collation",
    "pg_opclass",
    "pg_tablespace",
    "pg_user",
    # Redshift-specific views
    "svv_external_tables",
    "svv_external_columns",
    "svv_external_schemas",
]
