"""Storage backends. open_store() picks one from the scheme of storage.url."""
from tessera.storage.attempts import record_attempt
from tessera.storage.base import Store

__all__ = ["Store", "migrate", "open_store", "record_attempt"]


def open_store(storage_cfg):
    url = storage_cfg.url
    scheme = url.split(":", 1)[0].lower()
    if scheme in ("postgres", "postgresql"):
        from tessera.storage.postgres import PostgresStore

        return PostgresStore(url, pool_size=storage_cfg.pool_size, statement_timeout=storage_cfg.statement_timeout)
    if scheme == "sqlite":
        from tessera.storage.sqlite import SqliteStore

        return SqliteStore(url[len("sqlite://"):])
    raise ValueError("unsupported storage url: %s" % url)


def migrate(storage_cfg, dry_run=False):
    store = open_store(storage_cfg)
    try:
        return store.migrate(dry_run=dry_run)
    finally:
        store.close()
