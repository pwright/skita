import hashlib


def compute_topic_id(anchor: str | None, heading: str, source_path: str, line_no: int) -> str:
    if anchor:
        return anchor
    key = f"{source_path}:{heading}:{line_no}"
    return "~" + hashlib.sha256(key.encode()).hexdigest()[:8]


def compute_finding_id(rule: str, topic_id: str, evidence: str) -> str:
    key = f"{rule}:{topic_id}:{evidence}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
