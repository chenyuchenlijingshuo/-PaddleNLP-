import hashlib

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(raw: str) -> str:
    return generate_password_hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return check_password_hash(hashed, raw)


def content_dedup_hash(title: str, source: str, published_iso: str, url: str) -> str:
    s = f"{title or ''}|{source or ''}|{published_iso or ''}|{url or ''}"
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()[:64]
