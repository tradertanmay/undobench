"""Object Storage (S3-compatible) domain sandbox with multipart uploads and concurrency checks."""

from __future__ import annotations
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class PreconditionFailedError(RuntimeError):
    """Raised when an ETag/version precondition fails during conditional put."""
    pass


class ObjectStorageSandbox:
    """Simulates S3-compatible cloud object storage with versioning, ETag checks, and multipart uploads."""

    def __init__(self):
        self.buckets: Dict[str, Dict[str, Any]] = {}
        # bucket_name -> key -> ObjectRecord
        self.storage: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # upload_id -> MultipartUploadRecord
        self.active_multipart_uploads: Dict[str, Dict[str, Any]] = {}

    def seed_bucket(self, bucket_name: str) -> None:
        self.buckets[bucket_name] = {"name": bucket_name, "created_at": time.time()}
        self.storage.setdefault(bucket_name, {})

    def seed_object(self, bucket_name: str, key: str, content: str) -> None:
        self.seed_bucket(bucket_name)
        etag = hashlib.md5(content.encode("utf-8")).hexdigest()
        self.storage[bucket_name][key] = {
            "key": key,
            "content": content,
            "etag": etag,
            "version_id": uuid.uuid4().hex[:8],
            "size_bytes": len(content.encode("utf-8")),
            "updated_at": time.time(),
        }

    # --- Tool Callables (Exposed to Agents via ToolProxy) ---

    def put_object(
        self,
        bucket_name: str,
        key: str,
        content: str,
        if_match_etag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool: Upload object to bucket with optional ETag concurrency check."""
        if bucket_name not in self.storage:
            self.seed_bucket(bucket_name)

        existing = self.storage[bucket_name].get(key)
        if if_match_etag and existing:
            if existing["etag"] != if_match_etag:
                raise PreconditionFailedError(
                    f"ETag precondition failed for {bucket_name}/{key}: expected {if_match_etag}, found {existing['etag']}"
                )

        etag = hashlib.md5(content.encode("utf-8")).hexdigest()
        version_id = uuid.uuid4().hex[:8]
        self.storage[bucket_name][key] = {
            "key": key,
            "content": content,
            "etag": etag,
            "version_id": version_id,
            "size_bytes": len(content.encode("utf-8")),
            "updated_at": time.time(),
        }
        return {
            "bucket": bucket_name,
            "key": key,
            "etag": etag,
            "version_id": version_id,
            "size_bytes": len(content),
        }

    def delete_object(self, bucket_name: str, key: str) -> Dict[str, Any]:
        """Tool: Delete object from bucket."""
        if bucket_name in self.storage and key in self.storage[bucket_name]:
            del self.storage[bucket_name][key]
            return {"bucket": bucket_name, "key": key, "deleted": True}
        return {"bucket": bucket_name, "key": key, "deleted": False}

    def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> Dict[str, Any]:
        """Tool: Copy object atomically between keys or buckets."""
        if source_bucket not in self.storage or source_key not in self.storage[source_bucket]:
            raise ValueError(f"Source object {source_bucket}/{source_key} not found")

        source_obj = self.storage[source_bucket][source_key]
        return self.put_object(
            bucket_name=dest_bucket,
            key=dest_key,
            content=source_obj["content"],
        )

    def initiate_multipart_upload(self, bucket_name: str, key: str) -> Dict[str, Any]:
        """Tool: Initiate multipart archive upload."""
        upload_id = f"upload_{uuid.uuid4().hex[:12]}"
        self.active_multipart_uploads[upload_id] = {
            "upload_id": upload_id,
            "bucket": bucket_name,
            "key": key,
            "parts": {},
            "initiated_at": time.time(),
        }
        return {"upload_id": upload_id, "bucket": bucket_name, "key": key}

    def upload_part(self, upload_id: str, part_number: int, data: str) -> Dict[str, Any]:
        """Tool: Upload individual chunk of multipart upload."""
        if upload_id not in self.active_multipart_uploads:
            raise ValueError(f"Upload ID {upload_id} not found or expired")

        part_etag = hashlib.md5(data.encode("utf-8")).hexdigest()
        upload = self.active_multipart_uploads[upload_id]
        upload["parts"][part_number] = {"part_number": part_number, "data": data, "etag": part_etag}
        return {"upload_id": upload_id, "part_number": part_number, "etag": part_etag}

    def complete_multipart_upload(self, upload_id: str, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tool: Assemble uploaded parts into completed object."""
        if upload_id not in self.active_multipart_uploads:
            raise ValueError(f"Upload ID {upload_id} not found")

        upload = self.active_multipart_uploads.pop(upload_id)
        bucket = upload["bucket"]
        key = upload["key"]

        # Sort parts by part_number and combine
        sorted_parts = sorted(upload["parts"].values(), key=lambda p: p["part_number"])
        full_content = "".join(p["data"] for p in sorted_parts)
        return self.put_object(bucket_name=bucket, key=key, content=full_content)

    # --- Oracle Inspection Methods ---

    def query_object_exists(self, bucket_name: str, key: str) -> bool:
        return bucket_name in self.storage and key in self.storage[bucket_name]

    def query_object_content(self, bucket_name: str, key: str) -> Optional[str]:
        if self.query_object_exists(bucket_name, key):
            return self.storage[bucket_name][key]["content"]
        return None

    def query_object_count(self, bucket_name: str) -> int:
        return len(self.storage.get(bucket_name, {}))

    def get_full_state(self) -> Dict[str, Any]:
        return {
            "buckets": list(self.buckets.keys()),
            "storage": {
                b: {
                    k: {
                        "key": obj["key"],
                        "size_bytes": obj["size_bytes"],
                        "etag": obj["etag"],
                        "content": obj["content"],
                    }
                    for k, obj in objs.items()
                }
                for b, objs in self.storage.items()
            },
            "active_multipart_uploads_count": len(self.active_multipart_uploads),
        }

    def cleanup(self) -> None:
        self.buckets.clear()
        self.storage.clear()
        self.active_multipart_uploads.clear()
