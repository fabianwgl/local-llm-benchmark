"""Command-line entry point (`tessera <command>`)."""
import argparse
import json
import logging
import signal
import sys
import threading

from tessera import __version__
from tessera.config import ConfigError, load_config

log = logging.getLogger("tessera")

# argparse dest -> dotted configuration key
FLAG_KEYS = {
    "port": "api.port",
    "concurrency": "worker.concurrency",
    "queues": "worker.queues",
    "max_backoff": "retry.max_delay",
    "log_level": "logging.level",
}


def build_parser():
    parser = argparse.ArgumentParser(prog="tessera", description="durable job scheduler")
    parser.add_argument("--version", action="version", version="tessera " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the API, the workers and leader election")
    _common(serve)
    serve.add_argument("--port", type=int, help="HTTP port (api.port)")
    serve.add_argument("--concurrency", type=int, help="worker threads (worker.concurrency)")
    serve.add_argument("--queues", help="comma-separated queues to consume (worker.queues)")
    serve.add_argument("--max-backoff", metavar="DURATION",
                       help="upper bound for retry delays, e.g. 90s or 5m (retry.max_delay)")
    serve.add_argument("--no-api", action="store_true", help="run workers only")

    migrate = sub.add_parser("migrate", help="apply pending SQL migrations and exit")
    _common(migrate)
    migrate.add_argument("--dry-run", action="store_true", help="list pending migrations only")

    show = sub.add_parser("show-config", help="print the effective configuration as JSON")
    _common(show)
    return parser


def _common(parser):
    parser.add_argument("--config", metavar="PATH",
                        help="YAML file (default: $TESSERA_CONFIG, then /etc/tessera/tessera.yaml)")
    parser.add_argument("--log-level", help="DEBUG, INFO, WARNING or ERROR (logging.level)")


def flag_overrides(args):
    found = {}
    for dest, key in FLAG_KEYS.items():
        value = getattr(args, dest, None)
        if value is not None:
            found[key] = value
    return found


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config, cli=flag_overrides(args))
    except ConfigError as exc:
        print("tessera: %s" % exc, file=sys.stderr)
        return 2
    logging.basicConfig(level=cfg.logging.level, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if args.command == "show-config":
        print(json.dumps(cfg.as_dict(), indent=2, sort_keys=True, default=str))
        return 0
    if args.command == "migrate":
        from tessera.storage import migrate

        for name in migrate(cfg.storage, dry_run=args.dry_run):
            print(("pending " if args.dry_run else "applied ") + name)
        return 0
    return serve(cfg, api=not args.no_api)


def serve(cfg, api=True):
    from tessera.runtime import build_runtime

    runtime = build_runtime(cfg)
    stop = threading.Event()

    def _on_signal(signum, frame):
        log.info("signal %d received, shutting down", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    runtime.start(api=api)
    stop.wait()
    runtime.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
