"""Teacher resolutions of unsure answers, signed by the teacher session that made them (architecture.md §4).

The web layer signs a resolution with the server's resolution key after authenticating a teacher; the
OutcomeWriter verifies the signature and re-checks the teacher's role in the database before applying it.
"""
import dataclasses
import hashlib
import hmac
import json
import uuid

OUTCOMES = ("correct", "partial", "wrong")
MIN_KEY_BYTES = 32


class BadSignature(Exception):
    pass


@dataclasses.dataclass(frozen=True)
class TeacherResolution:
    queue_item_id: uuid.UUID
    teacher_id: uuid.UUID
    outcome: str
    note_hi: str | None
    signature: str

    def __post_init__(self):
        if self.outcome not in OUTCOMES:
            raise ValueError(f"a resolution settles an answer as one of {OUTCOMES}, got {self.outcome!r}")

    @staticmethod
    def _payload(queue_item_id, teacher_id, outcome, note_hi) -> bytes:
        return json.dumps({"queue_item_id": str(queue_item_id), "teacher_id": str(teacher_id),
                           "outcome": outcome, "note_hi": note_hi},
                          sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()

    @staticmethod
    def _check_key(key: bytes):
        if not isinstance(key, bytes) or len(key) < MIN_KEY_BYTES:
            raise ValueError(f"the resolution key must be at least {MIN_KEY_BYTES} bytes")

    @classmethod
    def sign(cls, *, key: bytes, queue_item_id, teacher_id, outcome, note_hi) -> "TeacherResolution":
        cls._check_key(key)
        q, t = uuid.UUID(str(queue_item_id)), uuid.UUID(str(teacher_id))
        sig = hmac.new(key, cls._payload(q, t, outcome, note_hi), hashlib.sha256).hexdigest()
        return cls(queue_item_id=q, teacher_id=t, outcome=outcome, note_hi=note_hi, signature=sig)

    def verify(self, key: bytes) -> bool:
        self._check_key(key)
        expected = hmac.new(key, self._payload(self.queue_item_id, self.teacher_id, self.outcome, self.note_hi),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, self.signature):
            raise BadSignature("teacher resolution signature does not verify")
        return True
