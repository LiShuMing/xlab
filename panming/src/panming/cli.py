"""HTTP CLI for the local Panming workspace."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import click
import httpx


@click.group()
@click.option("--server", default="http://127.0.0.1:8788", envvar="PANMING_SERVER_URL")
@click.pass_context
def main(ctx: click.Context, server: str) -> None:
    """盘铭：归档素材、生成日报与导出知识。"""
    ctx.obj = server.rstrip("/")


def request(server: str, path: str, *, method: str = "POST", **kwargs) -> dict:
    try:
        send = httpx.patch if method == "PATCH" else httpx.post
        response = send(server + "/api/v1" + path, timeout=30, **kwargs)
        response.raise_for_status()
        data = response.json()
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return data
    except httpx.HTTPError as error:
        raise click.ClickException(str(error)) from error


@main.group()
def capture() -> None:
    """收集原始素材。"""


@capture.command("file")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_obj
def file_capture(server: str, path: Path) -> None:
    with path.open("rb") as original:
        request(server, "/captures/files", files={"file": (path.name, original)})


@capture.command("note")
@click.option("--title", required=True)
@click.option("--text", "body", required=True)
@click.pass_obj
def note_capture(server: str, title: str, body: str) -> None:
    request(server, "/captures", json={"title": title, "content": body})


@capture.command("url")
@click.argument("url")
@click.option("--title", default="保存的链接")
@click.pass_obj
def url_capture(server: str, url: str, title: str) -> None:
    """归档链接（本版不自动抓取正文）。"""
    request(server, "/captures", json={"title": title, "url": url, "kind": "web_page"})


@main.command("report")
@click.option("--date", "day", required=True)
@click.pass_obj
def generate_report(server: str, day: str) -> None:
    request(server, "/reports/runs", json={"date": day})


def fetch(server: str, path: str):
    try:
        response = httpx.get(server + "/api/v1" + path, timeout=30)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        raise click.ClickException(str(error)) from error


@main.command("digest")
@click.argument("material_ids", nargs=-1, required=True)
@click.option("--revision", type=click.IntRange(min=1), help="仅单个素材可指定历史版本")
@click.option("--provider", type=click.Choice(["mock", "openai_compatible"]), default="mock")
@click.option("--allow-cloud", is_flag=True, help="明确同意将所选版本正文发送给已配置的 API")
@click.pass_obj
def submit_digest(
    server: str,
    material_ids: tuple[str, ...],
    revision: int | None,
    provider: str,
    allow_cloud: bool,
) -> None:
    """冻结来源后消化；真实模型需要素材授权与显式 --allow-cloud。"""
    if revision and len(material_ids) != 1:
        raise click.ClickException("指定历史版本时请只传一个素材 ID")
    refs = []
    for mid in material_ids:
        item = fetch(server, f"/objects/{mid}" + (f"?revision={revision}" if revision else ""))
        if item.get("object_kind") != "material":
            raise click.ClickException("只能消化素材")
        refs.append(
            {
                "material_id": item["id"],
                "material_revision": item["revision"],
                "blob_hash": item["blob_hash"],
            }
        )
    profile = cloud_profile(server) if provider == "openai_compatible" else None
    if profile and not allow_cloud:
        raise click.ClickException("云端消化需要 --allow-cloud，现有素材不会自动外发")
    request(
        server,
        "/digest/jobs",
        json={
            "source_refs": refs,
            "provider": provider,
            "cloud_consent": allow_cloud,
            "provider_profile": profile["profile_id"] if profile else None,
        },
    )


def cloud_profile(server: str) -> dict:
    profile = next(
        (
            p
            for p in fetch(server, "/processing")["processing"]["profiles"]
            if p["provider"] == "openai_compatible"
        ),
        None,
    )
    if not profile:
        raise click.ClickException("API 服务未配置或未启用，请检查 llm status")
    return profile


@main.group()
def llm() -> None:
    """查看模型服务的非敏感配置；不输出密钥。"""


@llm.command("status")
@click.pass_obj
def llm_status(server: str) -> None:
    click.echo(json.dumps(fetch(server, "/processing")["processing"], ensure_ascii=False, indent=2))


@main.group()
def material() -> None:
    """明确设置素材处理策略。"""


@material.command("policy")
@click.argument("material_id")
@click.option("--revision", type=click.IntRange(min=1), required=True)
@click.option("--policy", type=click.Choice(["local_only", "cloud_allowed"]), required=True)
@click.option("--confirm-cloud", is_flag=True, help="授权当前正文给已配置的服务/模型；不会立即外发")
@click.pass_obj
def material_policy(
    server: str, material_id: str, revision: int, policy: str, confirm_cloud: bool
) -> None:
    if policy == "cloud_allowed" and not confirm_cloud:
        raise click.ClickException("设置云端授权需要 --confirm-cloud")
    profile = cloud_profile(server) if policy == "cloud_allowed" else None
    request(
        server,
        f"/materials/{material_id}/policy",
        method="PATCH",
        json={
            "revision": revision,
            "processing_policy": policy,
            "provider_profile": profile["profile_id"] if profile else None,
        },
    )


@main.group()
def jobs() -> None:
    """查看、取消或手动重试持久任务。"""


@jobs.command("list")
@click.pass_obj
def list_jobs(server: str) -> None:
    click.echo(json.dumps(fetch(server, "/processing"), ensure_ascii=False, indent=2))


@jobs.command("cancel")
@click.argument("job_id")
@click.pass_obj
def cancel_job(server: str, job_id: str) -> None:
    request(server, f"/jobs/{job_id}/cancel", json={})


@jobs.command("retry")
@click.argument("job_id")
@click.option("--allow-cloud", is_flag=True, help="明确同意再次发送云端请求并消耗额度")
@click.pass_obj
def retry_job(server: str, job_id: str, allow_cloud: bool) -> None:
    profile = cloud_profile(server) if allow_cloud else None
    request(
        server,
        f"/jobs/{job_id}/retry",
        json={
            "cloud_consent": allow_cloud,
            "provider_profile": profile["profile_id"] if profile else None,
        },
    )


@main.command("export")
@click.argument("object_id")
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.option("--revision", type=click.IntRange(min=1))
@click.option(
    "--format", "file_format", type=click.Choice(["auto", "raw", "markdown"]), default="auto"
)
@click.pass_obj
def export(
    server: str, object_id: str, output: Path, revision: int | None, file_format: str
) -> None:
    try:
        query = f"?format={file_format}" + (f"&revision={revision}" if revision else "")
        response = httpx.get(f"{server}/api/v1/export/{object_id}{query}", timeout=30)
        response.raise_for_status()
        save_download(response, output)
        click.echo(f"已导出：{output}")
    except httpx.HTTPError as error:
        raise click.ClickException(str(error)) from error


def save_download(response: httpx.Response, output: Path) -> None:
    digest = response.headers.get("X-Content-SHA256")
    if digest and hashlib.sha256(response.content).hexdigest() != digest:
        raise click.ClickException("下载校验失败，未写文件")
    if output.exists():
        raise click.ClickException("目标文件已存在，请使用新路径")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent, prefix=".panming-download-", delete=False
        ) as out:
            temporary = Path(out.name)
            out.write(response.content)
            out.flush()
            os.fsync(out.fileno())
        os.link(temporary, output)  # Atomic no-clobber, including a racing writer.
    except OSError as error:
        raise click.ClickException(f"无法保存下载：{error}") from error
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


@main.group()
def workspace() -> None:
    """备份全部修订和原件，或恢复到空工作空间。"""


@workspace.command("backup")
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.pass_obj
def backup_workspace(server: str, output: Path) -> None:
    try:
        response = httpx.get(f"{server}/api/v1/workspace/backup", timeout=120)
        response.raise_for_status()
        save_download(response, output)
        click.echo(f"完整备份已校验保存：{output}")
    except httpx.HTTPError as error:
        raise click.ClickException(str(error)) from error


@workspace.command("restore")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_obj
def restore_workspace(server: str, archive: Path) -> None:
    """仅写入空工作空间；不删除或覆盖已有对象。"""
    with archive.open("rb") as source:
        request(server, "/workspace/restore", files={"file": (archive.name, source)})


@workspace.command("verify")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def verify_workspace(archive: Path) -> None:
    """本机校验清单、所有原件和引用，不向服务发送备份。"""
    from .backup import BackupError, inspect_archive

    try:
        metadata, files = inspect_archive(archive.read_bytes())
        click.echo(
            json.dumps(
                {
                    "valid": True,
                    "objects": len(metadata["objects"]),
                    "revisions": len(metadata["revisions"]),
                    "blobs": len(files),
                },
                ensure_ascii=False,
            )
        )
    except (BackupError, OSError) as error:
        raise click.ClickException(str(error)) from error


@main.command("demo")
@click.pass_obj
def demo(server: str) -> None:
    """添加明确标记的内置体验资料。"""
    request(server, "/demo")
