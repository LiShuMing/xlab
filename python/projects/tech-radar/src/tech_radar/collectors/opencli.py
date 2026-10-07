from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tech_radar.domain import Signal, Target


class OpenCliError(RuntimeError):
    pass


class OpenCliClient:
    def __init__(
        self,
        command: Sequence[str] | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self.command = tuple(command or self._detect_command())
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _detect_command() -> tuple[str, ...]:
        executable = shutil.which("opencli")
        windows_shim_from_wsl = bool(
            executable
            and os.name != "nt"
            and Path(executable).as_posix().startswith("/mnt/")
        )
        if (
            executable
            and not executable.lower().endswith((".cmd", ".bat"))
            and not windows_shim_from_wsl
        ):
            return (executable,)
        command_shell = shutil.which("cmd.exe") or os.environ.get("COMSPEC")
        if command_shell and (executable or shutil.which("opencli.cmd")):
            return (command_shell, "/d", "/s", "/c", "opencli")
        raise OpenCliError(
            "opencli was not found; install it with "
            "`npm install -g @jackwener/opencli`"
        )

    def run_json(self, arguments: Sequence[str]) -> Any:
        completed = self.run((*arguments, "-f", "json"))
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            preview = completed.stdout[:300].replace("\n", " ")
            raise OpenCliError(f"opencli returned invalid JSON: {preview}") from exc

    def run(self, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        current_no_proxy = environment.get("NO_PROXY", environment.get("no_proxy", ""))
        local_hosts = "localhost,127.0.0.1"
        environment["NO_PROXY"] = ",".join(
            part for part in (current_no_proxy, local_hosts) if part
        )
        working_directory: str | None = None
        if Path(self.command[0]).name.casefold() == "cmd.exe":
            if os.name == "nt":
                working_directory = os.environ.get("USERPROFILE", "C:\\")
            elif Path("/mnt/c").is_dir():
                working_directory = "/mnt/c"
        try:
            completed = subprocess.run(
                [*self.command, *arguments],
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                env=environment,
                cwd=working_directory,
            )
        except subprocess.TimeoutExpired as exc:
            raise OpenCliError(
                f"opencli timed out after {self.timeout_seconds} seconds"
            ) from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise OpenCliError(
                f"opencli exited with {completed.returncode}: {detail[:1000]}"
            )
        return completed


class OpenCliCollector:
    def __init__(
        self,
        client: OpenCliClient,
        *,
        require_read_only: bool = True,
        base_dir: Path | None = None,
    ) -> None:
        self.client = client
        self.require_read_only = require_read_only
        self.base_dir = base_dir or Path.cwd()
        self._capabilities: dict[tuple[str, str], Mapping[str, Any]] | None = None

    def collect(self, target: Target) -> list[Signal]:
        fixture = target.options.get("fixture")
        if fixture:
            fixture_path = Path(str(fixture))
            if not fixture_path.is_absolute():
                fixture_path = self.base_dir / fixture_path
            payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            records = _records(payload)
            signals: list[Signal] = []
            for record in records:
                tagged_record = dict(record)
                tagged_record["_fixture"] = True
                signals.append(_normalize(target, tagged_record))
            return signals

        self._validate_capability(target)
        subjects = target.options.get("subjects")
        if subjects is None:
            payload = self.client.run_json(
                (target.platform, target.command, *target.arguments)
            )
            return [_normalize(target, record) for record in _records(payload)]
        if not isinstance(subjects, list) or not all(
            isinstance(subject, str) and subject.strip() for subject in subjects
        ):
            raise OpenCliError(f"target {target.id} subjects must be strings")
        if not any("{subject}" in argument for argument in target.arguments):
            raise OpenCliError(
                f"target {target.id} arguments must contain {{subject}}"
            )

        signals: list[Signal] = []
        failures: list[str] = []
        for subject in subjects:
            arguments = tuple(
                argument.replace("{subject}", subject)
                for argument in target.arguments
            )
            try:
                payload = self.client.run_json(
                    (target.platform, target.command, *arguments)
                )
            except OpenCliError as exc:
                failures.append(f"{subject}: {exc}")
                continue
            for record in _records(payload):
                tagged_record = dict(record)
                tagged_record["_watch_subject"] = subject
                signals.append(_normalize(target, tagged_record))
        if not signals and failures:
            raise OpenCliError(
                f"all {target.id} subjects failed: {'; '.join(failures[:3])}"
            )
        return signals

    def _validate_capability(self, target: Target) -> None:
        if not self.require_read_only:
            return
        if self._capabilities is None:
            payload = self.client.run_json(("list",))
            if not isinstance(payload, list):
                raise OpenCliError("opencli registry JSON must be an array")
            self._capabilities = {
                (str(item.get("site")), str(item.get("name"))): item
                for item in payload
                if isinstance(item, Mapping)
            }
        capability = self._capabilities.get((target.platform, target.command))
        if capability is None:
            raise OpenCliError(
                f"unknown OpenCLI command: {target.platform} {target.command}"
            )
        access = str(capability.get("access", "")).casefold()
        if access != "read":
            raise OpenCliError(
                f"refusing non-read OpenCLI command: {target.platform} "
                f"{target.command} (access={access or 'unknown'})"
            )


def _records(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("items", "results", "data", "posts", "tweets"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, Mapping)]
        return [payload]
    raise OpenCliError(f"unsupported OpenCLI payload type: {type(payload).__name__}")


def _first(record: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _number(record: Mapping[str, Any], *keys: str) -> int | float | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                return float(value) if "." in value else int(value)
            except ValueError:
                continue
    return None


def _normalize(target: Target, record: Mapping[str, Any]) -> Signal:
    url = _first(record, "url", "permalink", "link")
    content = _first(record, "text", "body", "selftext", "content", "description")
    title = _first(record, "title", "name")
    if not title:
        title = content.replace("\n", " ")[:120]
    if not content:
        content = title
    author = _first(record, "author", "username", "screen_name", "user")
    if not author and target.command in {"tweets", "user-posts", "user-comments"}:
        author = target.arguments[0].lstrip("@") if target.arguments else ""
    if not author:
        author = _first(record, "subreddit") or "unknown"

    external_id = _first(record, "id", "external_id", "post_id", "tweet_id")
    if not external_id:
        stable_value = url or json.dumps(record, ensure_ascii=False, sort_keys=True)
        external_id = hashlib.sha256(stable_value.encode("utf-8")).hexdigest()[:24]

    metrics: dict[str, int | float] = {}
    metric_aliases = {
        "likes": ("likes", "like_count", "ups"),
        "retweets": ("retweets", "retweet_count"),
        "replies": ("replies", "reply_count", "comments", "num_comments"),
        "views": ("views", "view_count"),
        "score": ("score",),
        "bookmarks": ("bookmarks", "bookmark_count"),
    }
    for name, aliases in metric_aliases.items():
        value = _number(record, *aliases)
        if value is not None:
            metrics[name] = value

    media_value = record.get("media_urls", record.get("media", []))
    if isinstance(media_value, str):
        media = (media_value,)
    elif isinstance(media_value, list):
        media = tuple(str(item) for item in media_value if item)
    else:
        media = ()

    tags = target.tags
    if record.get("_fixture") and "demo" not in tags:
        tags = (*tags, "demo")

    return Signal(
        external_id=external_id,
        source_id=target.id,
        platform=target.platform,
        object_type=target.command,
        author=author,
        title=title,
        content=content,
        url=url,
        published_at=_first(record, "created_at", "published_at", "date") or None,
        tags=tags,
        metrics=metrics,
        media=media,
        priority=target.priority,
        raw=dict(record),
    )


def create_opencli_collector(options: dict[str, Any]) -> OpenCliCollector:
    raw_command = options.get("command")
    if raw_command is None:
        command = None
    elif isinstance(raw_command, str):
        command = (raw_command,)
    elif isinstance(raw_command, list) and all(
        isinstance(part, str) for part in raw_command
    ):
        command = tuple(raw_command)
    else:
        raise ValueError("collectors.opencli.command must be a string array")
    client = OpenCliClient(
        command=command,
        timeout_seconds=int(options.get("timeout_seconds", 120)),
    )
    return OpenCliCollector(
        client,
        require_read_only=bool(options.get("require_read_only", True)),
        base_dir=Path(str(options.get("_base_dir", Path.cwd()))),
    )
