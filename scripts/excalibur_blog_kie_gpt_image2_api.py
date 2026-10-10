#!/usr/bin/env python3
"""Run GPT Image 2 i2i through the Kie async HTTP API.

The cover pipeline prepares `cover/t2i-batch.json` with the exact
prompt/aspect_ratio/resolution payload. Evening comic covers use
`gpt-image-2-5-sunburst-image-to-image` plus a local mascot reference
(`canon: sunburst_i2i`). Legacy black-canvas batches still work as
text-to-image without input_urls. This script creates a Kie job, polls
for completion, and writes `cover/t2i-result.json` consumed by
`excalibur_blog_cover_black_apply.py`.

On terminal failCode=400 / «image fetch failed» (Kie crawler cannot reach WP
media even when Cloud shell gets HTTP 200), the script uploads a local
reference via Kie File Stream Upload once and recreates the task with that
downloadUrl — without rewriting the git-safe batch file.

On createTask transport failure before any taskId (Connection reset by peer /
Errno 104), the script waits and retries createTask once with the same batch.

On poll-window timeout (still waiting/generating past --max-wait): one final
recordInfo before KIE API BLOCKER. If that call shows terminal failCode=500 /
«try again later», the existing max-1 recreate path runs (INC-20260730-0834).
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from excalibur_blog_site_base import (
    SITE_BASE_PLACEHOLDER,
    expand_site_base,
    resolve_public_base_from_env,
)


DEFAULT_CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
DEFAULT_RECORD_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"
DEFAULT_FILE_UPLOAD_URL = "https://kieai.redpandaai.co/api/file-stream-upload"
DEFAULT_FILE_UPLOAD_PATH = "excalibur-blog/hero"
DEFAULT_FILE_UPLOAD_USER_AGENT = "ExcaliburBlogKieFallback/1.0"
MODEL_GPT_IMAGE_2_I2I = "gpt-image-2-image-to-image"
MODEL_GPT_IMAGE_2_T2I = "gpt-image-2-text-to-image"
MODEL_GPT_IMAGE_2_5_SUNBURST_I2I = "gpt-image-2-5-sunburst-image-to-image"
DEFAULT_I2I_MODEL = MODEL_GPT_IMAGE_2_5_SUNBURST_I2I
DEFAULT_MODEL = DEFAULT_I2I_MODEL
DEFAULT_T2I_MODEL = MODEL_GPT_IMAGE_2_T2I
DEFAULT_API_KEY_ENV = "KIE_API_KEY"
SUNBURST_CANON = "sunburst_i2i"
SUNBURST_ASPECT_RATIOS = frozenset(
    {
        "auto",
        "1:1",
        "3:2",
        "2:3",
        "4:3",
        "3:4",
        "5:4",
        "4:5",
        "16:9",
        "9:16",
        "2:1",
        "1:2",
        "3:1",
        "1:3",
        "21:9",
        "9:21",
        "27:16",
        "16:27",
        "9:8",
        "8:9",
    }
)
SUNBURST_1K_ONLY_ASPECTS = frozenset({"27:16", "16:27", "9:8", "8:9"})
SUNBURST_RESOLUTIONS = frozenset({"1K", "2K", "4K"})
SUNBURST_BACKGROUNDS = frozenset({"transparent", "opaque", "auto"})
MAX_SUNBURST_INPUT_URLS = 16
DEFAULT_POLL_INTERVAL_SECONDS = 15
DEFAULT_MAX_WAIT_SECONDS = 900
DEFAULT_MAX_CREATE_RETRIES = 1
DEFAULT_RETRY_WAIT_SECONDS = 15
DEFAULT_LOCAL_REFERENCE = "memory/cover/assets/cover-mascot.png"
DUMMY_INPUT_HOSTS = frozenset({"unused.invalid"})


class KieApiError(RuntimeError):
    """Raised for API or response-shape failures."""


class KieRetryableFail(KieApiError):
    """Terminal recordInfo fail that may warrant one new createTask (not re-poll)."""

    def __init__(self, fail_code: Any, fail_msg: Any, task_id: str) -> None:
        self.fail_code = fail_code
        self.fail_msg = fail_msg
        self.task_id = task_id
        super().__init__(
            f"Kie task failed (retryable): failCode={fail_code} failMsg={fail_msg} task_id={task_id}"
        )


class KieImageFetchFail(KieApiError):
    """Terminal fail because Kie could not fetch input_urls — File Upload recreate."""

    def __init__(self, fail_code: Any, fail_msg: Any, task_id: str) -> None:
        self.fail_code = fail_code
        self.fail_msg = fail_msg
        self.task_id = task_id
        super().__init__(
            f"Kie image fetch failed: failCode={fail_code} failMsg={fail_msg} task_id={task_id}"
        )


def _normalize_fail_code(fail_code: Any) -> str:
    code_s = str(fail_code if fail_code is not None else "").strip()
    if code_s.endswith(".0") and code_s[:-2].isdigit():
        code_s = code_s[:-2]
    return code_s


def is_retryable_server_fail(fail_code: Any, fail_msg: Any) -> bool:
    """True for transient Kie server fails: failCode=500 and/or «try again later».

    Does not apply to waiting/generating — only terminal state=fail.
    """
    code_s = _normalize_fail_code(fail_code)
    msg_s = str(fail_msg if fail_msg is not None else "").strip().lower()
    if code_s == "500":
        return True
    if "try again later" in msg_s:
        return True
    return False


def is_image_fetch_fail(fail_code: Any, fail_msg: Any) -> bool:
    """True when Kie cannot fetch input_urls (WP/bot block) and suggests File Upload.

    Local HTTP 200 on the same URL does not prove Kie-fetchability.
    """
    code_s = _normalize_fail_code(fail_code)
    msg_s = str(fail_msg if fail_msg is not None else "").strip().lower()
    if "image fetch failed" in msg_s:
        return True
    if "file upload api" in msg_s and ("fetch" in msg_s or "access" in msg_s):
        return True
    if code_s == "400" and ("fetch" in msg_s or "access settings" in msg_s):
        return True
    return False


def is_pre_task_connection_reset(exc: BaseException) -> bool:
    """True for TCP reset / peer reset before createTask returns a taskId.

    Safe to retry createTask once only when no taskId/task record exists yet.
    """
    text = str(exc).lower()
    if "connection reset" in text:
        return True
    if "errno 104" in text:
        return True
    reason = getattr(exc, "reason", None)
    if reason is not None:
        reason_s = str(reason).lower()
        if "connection reset" in reason_s or "errno 104" in reason_s:
            return True
        errno = getattr(reason, "errno", None)
        if errno == 104:
            return True
    return False


def project_root() -> Path:
    env_root = os.environ.get("EXCALIBUR_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_path(root: Path, article_dir_arg: str, path_arg: str) -> Path:
    article_dir = Path(article_dir_arg)
    if not article_dir.is_absolute():
        article_dir = root / article_dir
    path = Path(path_arg)
    if not path.is_absolute():
        path = article_dir / path
    return path


def http_json(method: str, url: str, api_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise KieApiError(f"Kie API HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise KieApiError(f"Kie API network error: {exc.reason}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise KieApiError(f"Kie API returned non-JSON response: {body[:500]}") from exc
    if not isinstance(parsed, dict):
        raise KieApiError("Kie API returned a non-object JSON response")
    return parsed


def require_success(response: dict[str, Any], action: str) -> None:
    if response.get("code") == 200:
        return
    msg = response.get("msg") or "unknown error"
    raise KieApiError(f"Kie API {action} failed: code={response.get('code')} msg={msg}")


def expand_input_urls(input_urls: list[Any]) -> list[str]:
    """Expand {{SITE_BASE}} in batch input_urls for the live Kie API call."""
    live = resolve_public_base_from_env()
    out: list[str] = []
    for raw in input_urls:
        url = str(raw or "").strip()
        if not url:
            continue
        if SITE_BASE_PLACEHOLDER in url:
            if not live:
                raise KieApiError(
                    f"batch input_urls contain {SITE_BASE_PLACEHOLDER} but PUBLIC_SITE_URL/WP_SITE_URL is unset"
                )
            url = expand_site_base(url, live)
        out.append(url)
    return out


def batch_model_hint(batch: dict[str, Any]) -> str:
    validation = batch.get("validation")
    if isinstance(validation, dict):
        hinted = str(validation.get("model") or "").strip()
        if hinted:
            return hinted
    return str(batch.get("model") or "").strip()


def resolve_kie_model(*, cli_model: str, batch: dict[str, Any], is_t2i: bool) -> str:
    cli = (cli_model or "").strip()
    if cli:
        return cli
    hinted = batch_model_hint(batch)
    if hinted:
        return hinted
    return DEFAULT_T2I_MODEL if is_t2i else DEFAULT_I2I_MODEL


def is_sunburst_i2i(model: str, canon: str = "") -> bool:
    return (
        str(model or "").strip() == MODEL_GPT_IMAGE_2_5_SUNBURST_I2I
        or str(canon or "").strip() == SUNBURST_CANON
    )


def _sunburst_geometry(args: dict[str, Any]) -> tuple[str, str, str | None]:
    aspect = str(args.get("aspect_ratio") or "16:9").strip() or "16:9"
    resolution = str(args.get("resolution") or "1K").strip() or "1K"
    background = str(args.get("background") or "").strip()
    if aspect not in SUNBURST_ASPECT_RATIOS:
        raise KieApiError(f"Unsupported Sunburst aspect_ratio={aspect!r}")
    if resolution not in SUNBURST_RESOLUTIONS:
        raise KieApiError(f"Unsupported Sunburst resolution={resolution!r}")
    if aspect in SUNBURST_1K_ONLY_ASPECTS and resolution in {"2K", "4K"}:
        raise KieApiError(
            f"Sunburst aspect_ratio={aspect} supports 1K only (got {resolution})"
        )
    if background and background not in SUNBURST_BACKGROUNDS:
        raise KieApiError(f"Unsupported Sunburst background={background!r}")
    return aspect, resolution, background or None


def batch_mcp_args(
    batch_path: Path,
    *,
    allow_text_to_image: bool = False,
    model: str = "",
) -> dict[str, Any]:
    batch = load_json(batch_path)
    jobs = batch.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 1:
        raise KieApiError(f"Expected exactly one job in {batch_path}")
    job = jobs[0]
    if not isinstance(job, dict):
        raise KieApiError(f"Invalid job entry in {batch_path}")
    args = job.get("mcp_args")
    if not isinstance(args, dict):
        raise KieApiError(f"Missing jobs[0].mcp_args in {batch_path}")

    prompt = str(args.get("prompt") or "").strip()
    input_urls = args.get("input_urls")
    if not prompt:
        raise KieApiError("Missing prompt in jobs[0].mcp_args")
    if len(prompt) > 20000:
        raise KieApiError("prompt exceeds 20,000 characters")

    canon = str(batch.get("canon") or "").strip()
    effective_model = resolve_kie_model(
        cli_model=model, batch=batch, is_t2i=False
    )
    sunburst = is_sunburst_i2i(effective_model, canon)

    # Evening canon: black-canvas text-to-image — no reference URLs.
    # Sunburst 2.5 is image-to-image and must not fall through to t2i.
    t2i = (not sunburst) and (
        bool(allow_text_to_image)
        or canon == "black_canvas_t2i"
        or not input_urls
    )
    if t2i and (not isinstance(input_urls, list) or not input_urls):
        return {
            "prompt": prompt,
            "aspect_ratio": args.get("aspect_ratio") or "16:9",
            "resolution": args.get("resolution") or "1K",
        }

    if not isinstance(input_urls, list) or not input_urls:
        raise KieApiError("Missing non-empty input_urls in jobs[0].mcp_args")
    if sunburst and len(input_urls) > MAX_SUNBURST_INPUT_URLS:
        raise KieApiError(
            f"Sunburst input_urls max {MAX_SUNBURST_INPUT_URLS}, got {len(input_urls)}"
        )
    expanded_urls = expand_input_urls(input_urls)
    if not expanded_urls:
        raise KieApiError("Missing non-empty input_urls in jobs[0].mcp_args after expand")
    payload: dict[str, Any] = {
        "prompt": prompt,
        "input_urls": expanded_urls,
        "aspect_ratio": args.get("aspect_ratio") or "auto",
        "resolution": args.get("resolution") or "1K",
    }
    if sunburst:
        aspect, resolution, background = _sunburst_geometry(args)
        payload["aspect_ratio"] = aspect
        payload["resolution"] = resolution
        if background:
            payload["background"] = background
    return payload


def _guess_mime(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def download_url_to_temp(url: str, dest: Path) -> Path:
    """Download a public image URL into dest (Cloud shell often succeeds where Kie crawler fails)."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": DEFAULT_FILE_UPLOAD_USER_AGENT, "Accept": "image/*,*/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()
    except urllib.error.HTTPError as exc:
        raise KieApiError(f"Failed to download reference for Kie upload: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise KieApiError(f"Failed to download reference for Kie upload: {exc.reason}") from exc
    if not body:
        raise KieApiError("Failed to download reference for Kie upload: empty body")
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if not suffix and content_type.startswith("image/"):
        suffix = "." + content_type.split("/", 1)[1].replace("jpeg", "jpg")
    if suffix and dest.suffix.lower() != suffix:
        dest = dest.with_suffix(suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return dest


def is_dummy_input_url(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").strip().lower()
    return host in DUMMY_INPUT_HOSTS or host.endswith(".invalid")


def resolve_local_reference_bytes(
    *,
    root: Path,
    expanded_input_urls: list[str],
    work_dir: Path,
    local_reference: str = DEFAULT_LOCAL_REFERENCE,
) -> tuple[Path, str]:
    """Prefer downloaded WP media, else local mascot PNG.

    Dummy hosts such as unused.invalid are skipped (git-safe placeholder
    until prefer_local_reference upload). Does not mutate committed batch files.
    """
    local_path = Path(local_reference)
    if not local_path.is_absolute():
        local_path = root / local_path

    for url in expanded_input_urls:
        if not url.startswith("https://"):
            continue
        if is_dummy_input_url(url):
            continue
        try:
            dest = work_dir / "kie-fetch-fallback-ref"
            downloaded = download_url_to_temp(url, dest)
            return downloaded, "downloaded_input_url"
        except KieApiError as exc:
            print(f"Kie fetch-fallback: WP/download skip ({exc}); trying local reference", flush=True)

    if not local_path.is_file():
        raise KieApiError(
            f"Kie image-fetch fallback needs a local reference file at {local_path} "
            "(or a downloadable expanded input_urls entry)"
        )
    return local_path, "local_cover_mascot"


def upload_file_stream(
    *,
    upload_url: str,
    api_key: str,
    file_path: Path,
    upload_path: str = DEFAULT_FILE_UPLOAD_PATH,
    file_name: str | None = None,
) -> str:
    """Upload binary via Kie File Stream Upload; return data.downloadUrl."""
    name = (file_name or file_path.name).strip() or "reference.png"
    mime = _guess_mime(file_path)
    boundary = "----ExcaliburKieUploadBoundary"
    file_bytes = file_path.read_bytes()
    parts: list[bytes] = []
    for field_name, value in (
        ("uploadPath", upload_path.strip().strip("/")),
        ("fileName", name),
    ):
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)

    # Cloudflare on kieai.redpandaai.co may return CF1010 / HTML challenge when
    # User-Agent is missing (B62 INC-20260719-2030). Always send a browser-like UA.
    request = urllib.request.Request(
        upload_url,
        data=body,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": DEFAULT_FILE_UPLOAD_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise KieApiError(f"Kie File Upload HTTP {exc.code}: {err_body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise KieApiError(f"Kie File Upload network error: {exc.reason}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KieApiError(f"Kie File Upload returned non-JSON: {raw[:500]}") from exc
    if not isinstance(parsed, dict):
        raise KieApiError("Kie File Upload returned a non-object JSON response")
    upload_ok = parsed.get("code") == 200 or parsed.get("success") is True
    if not upload_ok:
        raise KieApiError(
            f"Kie File Upload failed: code={parsed.get('code')} msg={parsed.get('msg')}"
        )
    data = parsed.get("data")
    if not isinstance(data, dict):
        raise KieApiError(f"Kie File Upload missing data object: {parsed}")
    download_url = str(data.get("downloadUrl") or data.get("fileUrl") or "").strip()
    if not download_url.startswith("https://"):
        raise KieApiError(f"Kie File Upload missing https downloadUrl: {data}")
    return download_url


def prepare_kie_hosted_input_urls(
    *,
    root: Path,
    article_dir: Path,
    api_key: str,
    expanded_input_urls: list[str],
    upload_url: str,
    upload_path: str,
    local_reference: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Upload reference once; return new input_urls + meta (batch file untouched)."""
    work_dir = article_dir / "cover" / ".kie-upload-tmp"
    ref_path, source = resolve_local_reference_bytes(
        root=root,
        expanded_input_urls=expanded_input_urls,
        work_dir=work_dir,
        local_reference=local_reference or DEFAULT_LOCAL_REFERENCE,
    )
    download_url = upload_file_stream(
        upload_url=upload_url,
        api_key=api_key,
        file_path=ref_path,
        upload_path=upload_path,
        file_name=ref_path.name,
    )
    meta = {
        "source": source,
        "upload_path": upload_path,
        "local_name": ref_path.name,
        "download_host": urllib.parse.urlparse(download_url).netloc,
    }
    # Best-effort cleanup of downloaded temp (keep committed assets).
    if source == "downloaded_input_url" and work_dir in ref_path.parents:
        try:
            ref_path.unlink(missing_ok=True)
        except OSError:
            pass
    return [download_url], meta


def maybe_prefer_local_reference_upload(
    *,
    root: Path,
    article_dir: Path,
    batch_path: Path,
    image_input: dict[str, Any],
    api_key: str,
    upload_url: str,
    upload_path: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """If batch asks for local style plate, upload it before first createTask."""
    batch = load_json(batch_path)
    if not batch.get("prefer_local_reference"):
        return image_input, None
    local_reference = str(batch.get("local_reference") or "").strip()
    if not local_reference:
        return image_input, None
    local_path = Path(local_reference)
    if not local_path.is_absolute():
        local_path = root / local_path
    if not local_path.is_file():
        raise KieApiError(f"prefer_local_reference set but file missing: {local_reference}")
    download_url = upload_file_stream(
        upload_url=upload_url,
        api_key=api_key,
        file_path=local_path,
        upload_path=upload_path,
        file_name=local_path.name,
    )
    meta = {
        "source": "prefer_local_reference",
        "upload_path": upload_path,
        "local_name": local_path.name,
        "download_host": urllib.parse.urlparse(download_url).netloc,
        "cover_hero_mode": batch.get("cover_hero_mode"),
    }
    updated = dict(image_input)
    updated["input_urls"] = [download_url]
    print(
        f"Kie prefer_local_reference: uploaded {local_path.name} "
        f"host={meta['download_host']} (skip host-face i2i)",
        flush=True,
    )
    return updated, meta


def create_task(
    *,
    create_url: str,
    api_key: str,
    model: str,
    image_input: dict[str, Any],
    callback_url: str,
) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "model": model,
        "input": image_input,
    }
    if callback_url:
        payload["callBackUrl"] = callback_url
    response = http_json("POST", create_url, api_key, payload)
    require_success(response, "createTask")
    task_id = ((response.get("data") or {}).get("taskId") or "").strip()
    if not task_id:
        raise KieApiError(f"Kie API createTask response missing data.taskId: {response}")
    return task_id, response


def query_task(*, record_url: str, api_key: str, task_id: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"taskId": task_id})
    separator = "&" if "?" in record_url else "?"
    response = http_json("GET", f"{record_url}{separator}{query}", api_key)
    require_success(response, "recordInfo")
    data = response.get("data")
    if not isinstance(data, dict):
        raise KieApiError(f"Kie API recordInfo response missing data object: {response}")
    return data


def parse_result_urls(result_json: Any) -> list[str]:
    if not result_json:
        return []
    if isinstance(result_json, str):
        try:
            parsed = json.loads(result_json)
        except json.JSONDecodeError as exc:
            raise KieApiError(f"Kie resultJson is not valid JSON: {result_json[:500]}") from exc
    elif isinstance(result_json, dict):
        parsed = result_json
    else:
        raise KieApiError("Kie resultJson has unsupported type")
    urls = parsed.get("resultUrls") or parsed.get("result_urls") or []
    if not isinstance(urls, list):
        raise KieApiError("Kie resultJson resultUrls is not an array")
    return [str(url).strip() for url in urls if str(url).strip()]


def classify_record_info(data: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    """Return data on success, raise typed fails on terminal fail, else None (non-terminal)."""
    state = str(data.get("state") or "").strip().lower()
    if state == "success":
        urls = parse_result_urls(data.get("resultJson"))
        if not urls:
            raise KieApiError("Kie task succeeded but resultJson has no resultUrls")
        return data
    if state == "fail":
        fail_code = data.get("failCode")
        fail_msg = data.get("failMsg")
        if is_image_fetch_fail(fail_code, fail_msg):
            raise KieImageFetchFail(fail_code, fail_msg, task_id)
        if is_retryable_server_fail(fail_code, fail_msg):
            raise KieRetryableFail(fail_code, fail_msg, task_id)
        raise KieApiError(f"Kie task failed: failCode={fail_code} failMsg={fail_msg}")
    return None


def poll_until_result(
    *,
    record_url: str,
    api_key: str,
    task_id: str,
    poll_interval: int,
    max_wait: int,
) -> dict[str, Any]:
    started = time.monotonic()
    last_state = ""
    while True:
        data = query_task(record_url=record_url, api_key=api_key, task_id=task_id)
        state = str(data.get("state") or "").strip().lower()
        if state != last_state:
            print(f"Kie task {task_id}: state={state or 'unknown'}")
            last_state = state

        terminal = classify_record_info(data, task_id)
        if terminal is not None:
            return terminal

        # waiting / generating / other non-terminal: keep polling this taskId only
        elapsed = time.monotonic() - started
        if elapsed >= max_wait:
            # INC-20260730-0834: one final recordInfo before timeout BLOCKER.
            # Late terminal 500 / image-fetch must enter recreate paths, not hard-stop.
            print(
                f"Kie task {task_id}: poll window exhausted ({max_wait}s); "
                "one final recordInfo before timeout BLOCKER",
                flush=True,
            )
            try:
                final_data = query_task(
                    record_url=record_url, api_key=api_key, task_id=task_id
                )
            except KieApiError as exc:
                raise KieApiError(
                    f"Kie task did not finish within {max_wait} seconds; task_id={task_id}"
                ) from exc
            final_state = str(final_data.get("state") or "").strip().lower()
            if final_state != last_state:
                print(f"Kie task {task_id}: state={final_state or 'unknown'} (final)")
            terminal = classify_record_info(final_data, task_id)
            if terminal is not None:
                return terminal
            raise KieApiError(
                f"Kie task did not finish within {max_wait} seconds; task_id={task_id}"
            )
        time.sleep(min(poll_interval, max(1, int(max_wait - elapsed))))


def result_record(task_data: dict[str, Any], task_id: str) -> dict[str, Any]:
    urls = parse_result_urls(task_data.get("resultJson"))
    url = urls[0]
    return {
        "url": url,
        "urls": urls,
        "task_id": task_id,
        "source": "kie-api",
        "model": task_data.get("model") or DEFAULT_MODEL,
        "state": task_data.get("state"),
        "costTime": task_data.get("costTime"),
        "completeTime": task_data.get("completeTime"),
        "createTime": task_data.get("createTime"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Create/poll a Kie GPT Image 2 job from cover/t2i-batch.json"
    )
    ap.add_argument("--article-dir", required=True)
    ap.add_argument("--batch", default="cover/t2i-batch.json")
    ap.add_argument("--result", default="cover/t2i-result.json")
    ap.add_argument("--task-record", default="cover/kie-image-task.json")
    ap.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)
    ap.add_argument("--create-url", default=DEFAULT_CREATE_URL)
    ap.add_argument("--record-url", default=DEFAULT_RECORD_URL)
    ap.add_argument(
        "--model",
        default="",
        help=(
            "Kie model id. Default: batch validation.model / batch.model, else "
            "gpt-image-2-5-sunburst-image-to-image, or gpt-image-2-text-to-image "
            "when batch canon is black_canvas_t2i / no input_urls."
        ),
    )
    ap.add_argument(
        "--text-to-image",
        action="store_true",
        help="Allow missing input_urls (evening black-canvas cover path)",
    )
    ap.add_argument("--callback-url", default=os.environ.get("KIE_CALLBACK_URL", "").strip())
    ap.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS)
    ap.add_argument("--max-wait", type=int, default=DEFAULT_MAX_WAIT_SECONDS)
    ap.add_argument(
        "--max-create-retries",
        type=int,
        default=DEFAULT_MAX_CREATE_RETRIES,
        help=(
            "After terminal failCode=500 / «try again later», create a new task this many times "
            "(default 1). Never blind-retries while state=waiting/generating; never re-polls a failed taskId."
        ),
    )
    ap.add_argument(
        "--retry-wait",
        type=int,
        default=DEFAULT_RETRY_WAIT_SECONDS,
        help="Seconds to wait before a new createTask after retryable terminal fail (default 15)",
    )
    ap.add_argument(
        "--file-upload-url",
        default=DEFAULT_FILE_UPLOAD_URL,
        help="Kie File Stream Upload endpoint for image-fetch fallback",
    )
    ap.add_argument(
        "--file-upload-path",
        default=DEFAULT_FILE_UPLOAD_PATH,
        help="uploadPath for Kie File Stream Upload (default excalibur-blog/hero)",
    )
    ap.add_argument(
        "--no-file-upload-fallback",
        action="store_true",
        help="Disable auto File Upload recreate on failCode=400 / image fetch failed",
    )
    ap.add_argument("--task-id", default="", help="Poll an existing Kie task instead of creating a new one")
    ap.add_argument("--create-only", action="store_true", help="Create task, write task record, and exit")
    ap.add_argument("--dry-run", action="store_true", help="Validate batch and print sanitized create payload")
    args = ap.parse_args()

    root = project_root()
    article_dir = Path(args.article_dir)
    if not article_dir.is_absolute():
        article_dir = root / article_dir
    batch_path = resolve_path(root, args.article_dir, args.batch)
    result_path = resolve_path(root, args.article_dir, args.result)
    task_record_path = resolve_path(root, args.article_dir, args.task_record)

    try:
        batch = load_json(batch_path)
        canon = str(batch.get("canon") or "").strip()
        hinted_t2i = canon == "black_canvas_t2i"
        model = resolve_kie_model(
            cli_model=args.model, batch=batch, is_t2i=hinted_t2i
        )
        image_input = batch_mcp_args(
            batch_path,
            allow_text_to_image=bool(args.text_to_image) or hinted_t2i,
            model=model,
        )
        is_t2i = "input_urls" not in image_input
        if is_t2i and not (args.model or "").strip() and not batch_model_hint(batch):
            model = DEFAULT_T2I_MODEL
        create_payload = {
            "model": model,
            "input": image_input,
        }
        if args.callback_url:
            create_payload["callBackUrl"] = args.callback_url

        if args.dry_run:
            print(json.dumps({"create_url": args.create_url, "payload": create_payload}, ensure_ascii=False, indent=2))
            return 0

        api_key = os.environ.get(args.api_key_env, "").strip()
        if not api_key:
            print(
                f"❌ KIE API BLOCKER: set {args.api_key_env} in Cloud Secrets/env; the key must not be committed or printed.",
                file=sys.stderr,
            )
            return 1

        prefer_meta = None
        if not is_t2i:
            image_input, prefer_meta = maybe_prefer_local_reference_upload(
                root=root,
                article_dir=article_dir,
                batch_path=batch_path,
                image_input=image_input,
                api_key=api_key,
                upload_url=args.file_upload_url,
                upload_path=args.file_upload_path,
            )

        task_id = args.task_id.strip()
        create_response: dict[str, Any] | None = None
        remaining_create_retries = max(0, int(args.max_create_retries))
        create_attempts = 0
        retry_from_fail: dict[str, Any] | None = None
        fetch_upload_fallback_done = bool(prefer_meta)
        fetch_upload_meta: dict[str, Any] | None = prefer_meta
        pre_task_connection_reset_retry_done = False

        while True:
            if not task_id:
                try:
                    task_id, create_response = create_task(
                        create_url=args.create_url,
                        api_key=api_key,
                        model=model,
                        image_input=image_input,
                        callback_url=args.callback_url,
                    )
                except KieApiError as exc:
                    # No taskId / no kie-image-task.json yet — one same-batch retry
                    # on TCP reset (INC-20260725-1631). Not a quality-redo.
                    if (
                        not pre_task_connection_reset_retry_done
                        and is_pre_task_connection_reset(exc)
                    ):
                        pre_task_connection_reset_retry_done = True
                        wait_s = max(0, int(args.retry_wait))
                        print(
                            f"Kie pre-taskId connection reset: {exc}; "
                            f"waiting {wait_s}s then one same-batch createTask retry "
                            "(not quality-redo; no MCP fallback)",
                            flush=True,
                        )
                        retry_from_fail = {
                            "task_id": "",
                            "failCode": None,
                            "failMsg": str(exc),
                            "retry_kind": "pre_task_connection_reset",
                        }
                        if wait_s:
                            time.sleep(wait_s)
                        continue
                    raise
                create_attempts += 1
                task_meta: dict[str, Any] = {
                    "task_id": task_id,
                    "source": "kie-api",
                    "model": model,
                    "state": "created",
                    "create_response": create_response,
                    "create_attempt": create_attempts,
                    "created_at_epoch": int(time.time()),
                }
                if retry_from_fail:
                    task_meta["retry_of"] = retry_from_fail
                if fetch_upload_meta:
                    task_meta["input_urls_via"] = "kie-file-upload"
                    task_meta["file_upload"] = fetch_upload_meta
                save_json(task_record_path, task_meta)
                print(f"Kie task created: task_id={task_id} (create_attempt={create_attempts})")

            if args.create_only:
                print(f"OK task_record={task_record_path}")
                return 0

            try:
                task_data = poll_until_result(
                    record_url=args.record_url,
                    api_key=api_key,
                    task_id=task_id,
                    poll_interval=max(1, args.poll_interval),
                    max_wait=max(1, args.max_wait),
                )
                break
            except KieImageFetchFail as exc:
                if args.no_file_upload_fallback or fetch_upload_fallback_done:
                    raise KieApiError(
                        f"Kie image fetch failed (File Upload fallback unavailable/exhausted): "
                        f"failCode={exc.fail_code} failMsg={exc.fail_msg} task_id={exc.task_id}"
                    ) from exc
                print(
                    f"Kie image-fetch fail on task_id={exc.task_id}: "
                    f"failCode={exc.fail_code} failMsg={exc.fail_msg}; "
                    "uploading reference via File Upload API then one new createTask "
                    "(batch file stays git-safe {{SITE_BASE}})",
                    flush=True,
                )
                save_json(
                    task_record_path,
                    {
                        "task_id": exc.task_id,
                        "source": "kie-api",
                        "model": model,
                        "state": "fail",
                        "failCode": exc.fail_code,
                        "failMsg": exc.fail_msg,
                        "retryable": True,
                        "retry_kind": "image_fetch_file_upload",
                        "updated_at_epoch": int(time.time()),
                    },
                )
                new_urls, fetch_upload_meta = prepare_kie_hosted_input_urls(
                    root=root,
                    article_dir=article_dir,
                    api_key=api_key,
                    expanded_input_urls=list(image_input.get("input_urls") or []),
                    upload_url=args.file_upload_url,
                    upload_path=args.file_upload_path,
                    local_reference=str(batch.get("local_reference") or "").strip() or None,
                )
                image_input = dict(image_input)
                image_input["input_urls"] = new_urls
                fetch_upload_fallback_done = True
                retry_from_fail = {
                    "task_id": exc.task_id,
                    "failCode": exc.fail_code,
                    "failMsg": exc.fail_msg,
                    "retry_kind": "image_fetch_file_upload",
                    "file_upload": fetch_upload_meta,
                }
                print(
                    f"Kie File Upload OK host={fetch_upload_meta.get('download_host')} "
                    f"source={fetch_upload_meta.get('source')}; recreating task",
                    flush=True,
                )
                # Do not re-poll the failed taskId; do not rewrite t2i-batch.json.
                task_id = ""
                create_response = None
                continue
            except KieRetryableFail as exc:
                if remaining_create_retries <= 0:
                    raise KieApiError(
                        f"Kie task failed after create retries exhausted: "
                        f"failCode={exc.fail_code} failMsg={exc.fail_msg} "
                        f"task_id={exc.task_id}. "
                        f"Batch ready for Director same-batch re-run on unchanged "
                        f"t2i-batch.json when Kie healthy; Cover must NOT invent "
                        f"a third createTask / raise --max-create-retries / softен / MCP "
                        f"(apply-only after Director success)."
                    ) from exc
                wait_s = max(0, int(args.retry_wait))
                print(
                    f"Kie retryable terminal fail on task_id={exc.task_id}: "
                    f"failCode={exc.fail_code} failMsg={exc.fail_msg}; "
                    f"waiting {wait_s}s then new createTask "
                    f"(create retries left={remaining_create_retries})",
                    flush=True,
                )
                save_json(
                    task_record_path,
                    {
                        "task_id": exc.task_id,
                        "source": "kie-api",
                        "model": model,
                        "state": "fail",
                        "failCode": exc.fail_code,
                        "failMsg": exc.fail_msg,
                        "retryable": True,
                        "retry_kind": "server_500",
                        "create_retries_left": remaining_create_retries,
                        "updated_at_epoch": int(time.time()),
                    },
                )
                remaining_create_retries -= 1
                retry_from_fail = {
                    "task_id": exc.task_id,
                    "failCode": exc.fail_code,
                    "failMsg": exc.fail_msg,
                    "retry_kind": "server_500",
                }
                if wait_s:
                    time.sleep(wait_s)
                # Do not re-poll the failed taskId — start a fresh createTask.
                task_id = ""
                create_response = None
                continue
        record = result_record(task_data, task_id)
        save_json(result_path, record)
        final_task: dict[str, Any] = {
            "task_id": task_id,
            "source": "kie-api",
            "model": task_data.get("model") or model,
            "state": task_data.get("state"),
            "create_attempts": create_attempts,
            "result_path": str(result_path.relative_to(root) if result_path.is_relative_to(root) else result_path),
            "updated_at_epoch": int(time.time()),
        }
        if fetch_upload_fallback_done:
            final_task["file_upload_fallback"] = True
            if fetch_upload_meta:
                final_task["file_upload"] = fetch_upload_meta
        save_json(task_record_path, final_task)
        print(f"OK url={record['url']}")
        print(f"OK result={result_path}")
        return 0
    except KieApiError as exc:
        print(f"❌ KIE API BLOCKER: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
