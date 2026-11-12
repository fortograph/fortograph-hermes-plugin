"""Tool handlers for the Fortograph plugin.

Uploads local images to a remote Fortograph selective-encryption API and saves
the returned image. Uses only the Python standard library so it runs inside the
Hermes interpreter without extra dependencies.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://fortograph.selectiveencryption.com"
DEFAULT_TIMEOUT = 120
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
USER_AGENT = "Hermes-Fortograph/1.1"

_REDACTION_ACTIONS = {"fortographthumbnail", "fortograph", "fortographregiononly"}
_UNREDACTION_ACTIONS = {
    "unfortographthumbnail",
    "unfortograph",
    "unfortographregiononly",
}

# Image signatures accepted for upload and for writing results back. Content is
# sniffed by magic bytes so a model-supplied path cannot exfiltrate a text file
# (e.g. ~/.hermes/.env or an SSH key) that merely has an image-looking name.
_IMAGE_MAGIC = (
    b"\xff\xd8\xff",       # JPEG
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"GIF87a",
    b"GIF89a",
    b"BM",                 # BMP
    b"II*\x00",            # TIFF (little-endian)
    b"MM\x00*",            # TIFF (big-endian)
)


def _is_image_header(header: bytes) -> bool:
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return True
    return any(header.startswith(magic) for magic in _IMAGE_MAGIC)


_CTX = None
_ENDPOINT_CACHE: dict[str, str] = {}


def configure(ctx) -> None:
    global _CTX
    _CTX = ctx


def _setting(key: str, default=None):
    if _CTX is not None:
        try:
            return _CTX.get_config(key, default=default)
        except Exception:
            pass
    return default


def _secret(name: str):
    """Resolve a secret only through Hermes's profile-scoped secret scope.

    Deliberately no bare ``os.environ`` fallback: under gateway multiplexing that
    can pick up another profile's value. ``get_secret`` already honours the
    active profile's ``.env``/process env for single-profile deployments.
    """
    try:
        from agent.secret_scope import get_secret

        return get_secret(name) or ""
    except Exception:
        return ""


def _base_url() -> str:
    value = _setting("base_url") or os.environ.get("FORTOGRAPH_BASE_URL") or DEFAULT_BASE_URL
    return str(value).rstrip("/")


def _candidate_endpoints(base: str) -> list[str]:
    """Return API URL candidates for a base URL, whether it is a host root or
    already includes the /Fortograph servlet context."""
    base = base.rstrip("/")
    if base.endswith("/api/image"):
        return [base]
    candidates: list[str] = []

    def add(url: str) -> None:
        if url not in candidates:
            candidates.append(url)

    add(base + "/api/image")
    if base.lower().endswith("/fortograph"):
        add(base[: -len("/Fortograph")] + "/api/image")
    else:
        add(base + "/Fortograph/api/image")
    return candidates


def _probe(url: str):
    """Return the HTTP status of a bodyless POST, or None when unreachable.

    An empty POST is used instead of GET because the public host serves its SPA
    (HTTP 200) for unknown GET paths, while the real API answers POST with a
    non-404/405 status. A 404 or 405 therefore means the URL is not the API.
    """
    request = Request(
        url,
        data=b"",
        method="POST",
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "Content-Length": "0",
        },
    )
    try:
        with urlopen(request, timeout=min(_timeout(), 10)) as response:
            return response.status
    except HTTPError as exc:
        return exc.code
    except Exception:
        return None


def _endpoint() -> str:
    """Resolve the working /api/image endpoint and cache it per base URL."""
    base = _base_url()
    cached = _ENDPOINT_CACHE.get(base)
    if cached:
        return cached
    candidates = _candidate_endpoints(base)
    for candidate in candidates:
        status = _probe(candidate)
        if status is not None and status not in (404, 405):
            _ENDPOINT_CACHE[base] = candidate
            return candidate
    return candidates[0]


def _timeout() -> float:
    try:
        return max(1.0, float(_setting("timeout", DEFAULT_TIMEOUT)))
    except (TypeError, ValueError):
        return float(DEFAULT_TIMEOUT)


def _resolve_password(args: dict) -> str:
    password = args.get("password")
    if password:
        return str(password)
    return _secret("FORTOGRAPH_PASSWORD") or ""


def _normalize_action(action, allowed: set, default: str) -> str:
    value = str(action or default).strip().lower().replace("_", "").replace("-", "")
    if value not in allowed:
        raise ValueError(
            "Unsupported action %r; expected one of: %s"
            % (action, ", ".join(sorted(allowed)))
        )
    return value


def _normalize_regions(regions) -> dict:
    if isinstance(regions, str):
        regions = json.loads(regions)
    if isinstance(regions, dict):
        regions = regions.get("regionOfInterest", [])
    if not isinstance(regions, list) or not regions:
        raise ValueError("regions must be a non-empty list of shapes")

    normalized = []
    for index, region in enumerate(regions):
        if not isinstance(region, dict):
            raise ValueError("regions[%d] must be an object" % index)
        shape = region.get("shape") or "rectangle"
        coordinates = region.get("coordinates") or {}
        if not isinstance(coordinates, dict):
            raise ValueError("regions[%d].coordinates must be an object" % index)
        item = {
            "shape": shape,
            "color": region.get("color") or "#000000",
            "coordinates": coordinates,
        }
        for extra in ("text", "fontSize", "fontType"):
            if region.get(extra) is not None:
                item[extra] = region[extra]
        normalized.append(item)
    return {"regionOfInterest": normalized}


def _multipart(fields: dict, file_name: str, file_bytes: bytes):
    boundary = "----HermesFortograph" + uuid.uuid4().hex
    content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    body = bytearray()
    for key, value in fields.items():
        body += ("--%s\r\n" % boundary).encode()
        body += ('Content-Disposition: form-data; name="%s"\r\n\r\n' % key).encode()
        body += str(value).encode("utf-8") + b"\r\n"
    body += ("--%s\r\n" % boundary).encode()
    body += (
        'Content-Disposition: form-data; name="image"; filename="%s"\r\n'
        % os.path.basename(file_name)
    ).encode()
    body += ("Content-Type: %s\r\n\r\n" % content_type).encode()
    body += file_bytes + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()
    return boundary, bytes(body)


def _content_disposition_name(header: str) -> str:
    if not header:
        return ""
    if "filename*=UTF-8''" in header:
        name = header.split("filename*=UTF-8''", 1)[1].split(";")[0].strip().strip('"')
    elif "filename=" in header:
        name = header.split("filename=", 1)[1].split(";")[0].strip().strip('"')
    else:
        return ""
    return os.path.basename(name)


def _allowed_output_roots(input_path: str) -> list[str]:
    """Directories a result may be written into.

    The input image's own directory, plus the user-configured ``output_dir``
    setting (never a model-supplied value).
    """
    roots = [os.path.realpath(os.path.dirname(os.path.abspath(input_path)))]
    configured = _setting("output_dir")
    if configured:
        roots.append(os.path.realpath(os.path.expanduser(str(configured))))
    return roots


def _confined_output(input_path: str, output_path, default_name: str) -> str:
    """Resolve the write target and refuse anything outside the allowed roots."""
    if output_path:
        target = os.path.expanduser(str(output_path))
        if os.path.isdir(target):
            target = os.path.join(target, default_name)
    else:
        target = os.path.join(os.path.dirname(os.path.abspath(input_path)), default_name)
    target = os.path.abspath(target)

    target_dir = os.path.realpath(os.path.dirname(target))
    if not any(
        target_dir == root or target_dir.startswith(root + os.sep)
        for root in _allowed_output_roots(input_path)
    ):
        raise ValueError(
            "refusing to write outside the input image's directory or the "
            "configured output_dir: %s" % target
        )

    if os.path.islink(target):
        raise ValueError("refusing to write through a symlink: %s" % target)
    if os.path.exists(target):
        if not os.path.isfile(target):
            raise ValueError("refusing to overwrite a non-regular file: %s" % target)
        with open(target, "rb") as handle:
            if not _is_image_header(handle.read(16)):
                raise ValueError(
                    "refusing to overwrite an existing non-image file: %s" % target
                )

    return os.path.join(target_dir, os.path.basename(target))


def _save_output(input_path: str, output_path, default_name: str, data: bytes) -> str:
    # Never write arbitrary server bytes to disk: the response must itself be
    # an image (the API always answers with one).
    if not _is_image_header(data[:16]):
        raise ValueError("server response is not a recognized image; refusing to write it")
    target = _confined_output(input_path, output_path, default_name)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as handle:
        handle.write(data)
    return target


def _post_image(image_path: str, action: str, password: str, shapes_json) -> dict:
    if not image_path:
        raise ValueError("image_path is required")
    path = os.path.expanduser(str(image_path))
    if not os.path.isfile(path):
        raise ValueError("image not found: %s" % path)
    size = os.path.getsize(path)
    if size == 0:
        raise ValueError("image is empty: %s" % path)
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(
            "image is %.1f MB; the Fortograph API accepts at most 10 MB"
            % (size / (1024 * 1024))
        )
    if not password:
        raise ValueError(
            "a password is required (pass it explicitly or set FORTOGRAPH_PASSWORD)"
        )

    fields = {"password": password, "action": action}
    if shapes_json is not None:
        fields["shapes"] = json.dumps(shapes_json)

    with open(path, "rb") as handle:
        file_bytes = handle.read()

    if not _is_image_header(file_bytes[:16]):
        raise ValueError(
            "not a recognized image (JPEG/PNG/GIF/WEBP/BMP/TIFF required): %s" % path
        )

    base = _base_url()
    cached = _ENDPOINT_CACHE.get(base)
    candidates = [cached] if cached else _candidate_endpoints(base)
    last_status = None
    last_message = ""

    for index, endpoint in enumerate(candidates):
        boundary, body = _multipart(fields, path, file_bytes)
        request = Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "multipart/form-data; boundary=%s" % boundary,
                "Content-Length": str(len(body)),
                "Accept": "image/*, application/json",
                "User-Agent": USER_AGENT,
            },
        )

        try:
            with urlopen(request, timeout=_timeout()) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "")
                disposition = response.headers.get("Content-Disposition", "")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            last_status = exc.code
            try:
                parsed = json.loads(detail)
                last_message = parsed.get("error") or parsed.get("message") or detail
            except Exception:
                last_message = detail
            if exc.code in (404, 405) and index < len(candidates) - 1:
                continue
            raise RuntimeError(
                "Fortograph API returned HTTP %s: %s" % (exc.code, last_message)
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                "cannot reach Fortograph at %s: %s" % (endpoint, exc.reason)
            ) from exc

        if "json" in content_type.lower():
            detail = data.decode("utf-8", "replace")
            try:
                message = json.loads(detail).get("error") or detail
            except Exception:
                message = detail
            raise RuntimeError("Fortograph API error: %s" % message)

        _ENDPOINT_CACHE[base] = endpoint
        return {
            "data": data,
            "content_type": content_type,
            "disposition": disposition,
            "endpoint": endpoint,
        }

    raise RuntimeError(
        "Fortograph API not found under %s (last HTTP %s: %s)"
        % (base, last_status, last_message)
    )


def _result(payload: dict) -> str:
    return json.dumps(payload)


def fortograph_status(args: dict, **kwargs) -> str:
    try:
        endpoint = _endpoint()
        status = None
        try:
            request = Request(
                endpoint,
                method="GET",
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            )
            with urlopen(request, timeout=min(_timeout(), 30)) as response:
                status = response.status
        except HTTPError as exc:
            status = exc.code
        except URLError as exc:
            result = {
                "ok": False,
                "base_url": _base_url(),
                "endpoint": endpoint,
                "reachable": False,
                "api_ok": False,
                "status": None,
                "error": "cannot reach %s: %s" % (endpoint, exc.reason),
            }
            return _result(result)

        api_ok = status is not None and status != 404
        result = {
            "ok": api_ok,
            "base_url": _base_url(),
            "endpoint": endpoint,
            "reachable": status is not None,
            "api_ok": api_ok,
            "status": status,
        }
        return _result(result)
    except Exception as exc:  # noqa: BLE001 - handlers must never raise
        return _result(
            {
                "ok": False,
                "base_url": _base_url(),
                "error": "%s: %s" % (type(exc).__name__, exc),
            }
        )


def fortograph_redact(args: dict, **kwargs) -> str:
    try:
        action = _normalize_action(args.get("action"), _REDACTION_ACTIONS, "fortographthumbnail")
        shapes = _normalize_regions(args.get("regions") or args.get("shapes"))
        password = _resolve_password(args)
        response = _post_image(args.get("image_path", ""), action, password, shapes)
        name = _content_disposition_name(response["disposition"]) or (
            os.path.splitext(os.path.basename(str(args.get("image_path"))))[0]
            + "_fortographed"
            + (os.path.splitext(str(args.get("image_path")))[1] or ".jpg")
        )
        output = _save_output(
            args.get("image_path", ""), args.get("output_path"), name, response["data"]
        )
        return _result(
            {
                "ok": True,
                "action": action,
                "input": os.path.abspath(os.path.expanduser(str(args.get("image_path")))),
                "output": output,
                "bytes": len(response["data"]),
                "content_type": response["content_type"],
                "sha256": hashlib.sha256(response["data"]).hexdigest(),
                "base_url": _base_url(),
            }
        )
    except Exception as exc:  # noqa: BLE001 - handlers must never raise
        return _result({"ok": False, "error": str(exc), "type": type(exc).__name__})


def fortograph_unredact(args: dict, **kwargs) -> str:
    try:
        action = _normalize_action(args.get("action"), _UNREDACTION_ACTIONS, "unfortographthumbnail")
        password = _resolve_password(args)
        response = _post_image(args.get("image_path", ""), action, password, None)
        name = _content_disposition_name(response["disposition"]) or (
            os.path.splitext(os.path.basename(str(args.get("image_path"))))[0]
            + "_unfortographed"
            + (os.path.splitext(str(args.get("image_path")))[1] or ".jpg")
        )
        output = _save_output(
            args.get("image_path", ""), args.get("output_path"), name, response["data"]
        )
        return _result(
            {
                "ok": True,
                "action": action,
                "input": os.path.abspath(os.path.expanduser(str(args.get("image_path")))),
                "output": output,
                "bytes": len(response["data"]),
                "content_type": response["content_type"],
                "sha256": hashlib.sha256(response["data"]).hexdigest(),
                "base_url": _base_url(),
            }
        )
    except Exception as exc:  # noqa: BLE001 - handlers must never raise
        return _result({"ok": False, "error": str(exc), "type": type(exc).__name__})
