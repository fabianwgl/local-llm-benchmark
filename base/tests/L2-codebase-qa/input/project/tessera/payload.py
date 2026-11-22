"""Job payload encoding and the payload size policy."""
import json

from tessera.errors import PayloadTooLarge
from tessera.models import StoredPayload


def encode(payload):
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def decode(blob):
    return json.loads(blob.decode("utf-8"))


def prepare_payload(payload, jobs_cfg, store):
    """Encode `payload` for storage according to jobs.max_payload_bytes and jobs.payload_overflow."""
    blob = encode(payload)
    limit = jobs_cfg.max_payload_bytes
    if len(blob) <= limit:
        return StoredPayload(inline=blob, size=len(blob))
    if jobs_cfg.payload_overflow == "spill":
        return StoredPayload(ref=store.spill_payload(blob), size=len(blob))
    raise PayloadTooLarge("payload is %d bytes; the limit is %d" % (len(blob), limit))


def load_payload(job, store):
    if job.payload_ref is not None:
        return decode(store.read_blob(job.payload_ref))
    return decode(job.payload_inline)
