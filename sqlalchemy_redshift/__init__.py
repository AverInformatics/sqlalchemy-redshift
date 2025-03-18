
from importlib.metadata import distribution, PackageNotFoundError, version
from packaging.version import parse

for package in ['psycopg2', 'psycopg2-binary', 'psycopg2cffi']:
    try:
        dist = distribution(package)
        if parse(dist.version) < parse('2.5'):
            raise ImportError('Minimum required version for psycopg2 is 2.5')
        break
    except PackageNotFoundError:
        pass


__version__ = distribution('sqlalchemy-redshift').version

from sqlalchemy.dialects import registry  # noqa

registry.register(
    "redshift", "sqlalchemy_redshift.dialect",
    "RedshiftDialect_psycopg2"
)
registry.register(
    "redshift.psycopg2", "sqlalchemy_redshift.dialect",
    "RedshiftDialect_psycopg2"
)
registry.register(
    'redshift+psycopg2cffi', 'sqlalchemy_redshift.dialect',
    'RedshiftDialect_psycopg2cffi',
)

registry.register(
    "redshift+redshift_connector", "sqlalchemy_redshift.dialect",
    "RedshiftDialect_redshift_connector"
)
