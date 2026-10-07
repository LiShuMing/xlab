from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ArticlePayload:
    article_id: str
    version_id: str
    title: str
    summary: str
    body_markdown: str
    topic: str


@dataclass(frozen=True, slots=True)
class DeliveryManifest:
    id: str
    platform: str
    version: str
    capabilities: tuple[str, ...]
    manual_confirmation_required: bool


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    kind: str
    path: Path
    metadata: dict[str, Any]


class DeliveryAdapter(Protocol):
    manifest: DeliveryManifest

    def prepare(
        self,
        article: ArticlePayload,
        output_directory: Path,
        ledger_path: Path,
    ) -> tuple[ArtifactSpec, ...]: ...

    def preview(
        self,
        article: ArticlePayload,
        output_directory: Path,
        artifacts: tuple[ArtifactSpec, ...],
    ) -> ArtifactSpec: ...


class BlogMarkdownAdapter:
    manifest = DeliveryManifest(
        id="blog-markdown",
        platform="blog",
        version="1.0.0",
        capabilities=("prepare", "preview", "record-published"),
        manual_confirmation_required=True,
    )

    def prepare(
        self,
        article: ArticlePayload,
        output_directory: Path,
        ledger_path: Path,
    ) -> tuple[ArtifactSpec, ...]:
        del ledger_path
        output_directory.mkdir(parents=True, exist_ok=True)
        markdown = output_directory / "article.md"
        markdown.write_text(article.body_markdown, encoding="utf-8")
        metadata = output_directory / "manifest.json"
        metadata.write_text(
            json.dumps(
                {
                    "adapter": self.manifest.id,
                    "article_id": article.article_id,
                    "version_id": article.version_id,
                    "title": article.title,
                    "status": "prepared",
                    "manual_confirmation_required": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return (
            ArtifactSpec("blog-markdown", markdown, {"mime": "text/markdown"}),
            ArtifactSpec("manifest", metadata, {"mime": "application/json"}),
        )

    def preview(
        self,
        article: ArticlePayload,
        output_directory: Path,
        artifacts: tuple[ArtifactSpec, ...],
    ) -> ArtifactSpec:
        del artifacts
        preview = output_directory / "preview.html"
        body = html.escape(article.body_markdown)
        preview.write_text(
            _preview_document(
                article.title,
                f'<pre class="markdown">{body}</pre>',
                "Blog Markdown · manual publication",
            ),
            encoding="utf-8",
        )
        return ArtifactSpec("preview-html", preview, {"mime": "text/html"})


class XiaohongshuPackageAdapter:
    manifest = DeliveryManifest(
        id="xiaohongshu-package",
        platform="xiaohongshu",
        version="1.0.0",
        capabilities=("prepare", "validate", "preview", "record-published"),
        manual_confirmation_required=True,
    )

    def prepare(
        self,
        article: ArticlePayload,
        output_directory: Path,
        ledger_path: Path,
    ) -> tuple[ArtifactSpec, ...]:
        output_directory.mkdir(parents=True, exist_ok=True)
        image_directory = output_directory / "images"
        image_directory.mkdir(parents=True, exist_ok=True)
        title = _truncate_weighted(article.title, 38)
        tags = _tags(article.topic)
        body = _xiaohongshu_body(article, tags)
        _validate_xiaohongshu(title, body, tags)

        source = output_directory / "source.md"
        source.write_text(article.body_markdown, encoding="utf-8")
        copy_json = output_directory / "copy.json"
        copy_json.write_text(
            json.dumps(
                {"title": title, "body": body, "tags": tags},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        title_file = output_directory / "title.txt"
        title_file.write_text(title, encoding="utf-8")
        content_file = output_directory / "content.txt"
        content_file.write_text(
            f"{body}\n\n" + " ".join(f"#{tag}" for tag in tags),
            encoding="utf-8",
        )
        images = _render_cards(article, image_directory)
        fingerprint = _package_fingerprint(title, body, tags, source, images)
        manifest_path = output_directory / "manifest.json"
        manifest = {
            "adapter": self.manifest.id,
            "fingerprint": fingerprint,
            "source": str(source.resolve()),
            "source_sha256": _file_hash(source),
            "copy_json": str(copy_json.resolve()),
            "title_file": str(title_file.resolve()),
            "content_file": str(content_file.resolve()),
            "images": [
                {"path": str(path.resolve()), "sha256": _file_hash(path)}
                for path in images
            ],
            "visibility": "manual-review",
            "status": "prepared",
            "ledger": str(ledger_path.resolve()),
            "manual_confirmation_required": True,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _record_ledger(ledger_path, fingerprint, manifest_path, "prepared")
        artifacts = [
            ArtifactSpec("source-markdown", source, {"mime": "text/markdown"}),
            ArtifactSpec("xhs-copy", copy_json, {"mime": "application/json"}),
            ArtifactSpec("title", title_file, {"mime": "text/plain"}),
            ArtifactSpec("content", content_file, {"mime": "text/plain"}),
            ArtifactSpec("manifest", manifest_path, {"mime": "application/json"}),
        ]
        artifacts.extend(
            ArtifactSpec(
                f"image-{index:02d}", path, {"mime": "image/png", "order": index}
            )
            for index, path in enumerate(images, start=1)
        )
        return tuple(artifacts)

    def preview(
        self,
        article: ArticlePayload,
        output_directory: Path,
        artifacts: tuple[ArtifactSpec, ...],
    ) -> ArtifactSpec:
        copy_path = next(item.path for item in artifacts if item.kind == "xhs-copy")
        copy = json.loads(copy_path.read_text(encoding="utf-8"))
        images = [
            item.path
            for item in artifacts
            if item.kind.startswith("image-")
        ]
        image_markup = "".join(
            f'<img src="data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}" '
            f'alt="card {index}">'
            for index, path in enumerate(images, start=1)
        )
        content = (
            f'<div class="phone"><div class="cards">{image_markup}</div>'
            f'<h2>{html.escape(copy["title"])}</h2>'
            f'<p>{html.escape(copy["body"]).replace(chr(10), "<br>")}</p>'
            f'<div class="tags">'
            + " ".join(f"#{html.escape(tag)}" for tag in copy["tags"])
            + "</div></div>"
        )
        preview = output_directory / "preview.html"
        preview.write_text(
            _preview_document(
                article.title,
                content,
                "小红书预览 · visibility and Publish require manual confirmation",
            ),
            encoding="utf-8",
        )
        return ArtifactSpec("preview-html", preview, {"mime": "text/html"})


def create_delivery_adapters() -> dict[str, DeliveryAdapter]:
    adapters: tuple[DeliveryAdapter, ...] = (
        BlogMarkdownAdapter(),
        XiaohongshuPackageAdapter(),
    )
    return {adapter.manifest.platform: adapter for adapter in adapters}


def mark_xiaohongshu_published(manifest_path: Path, external_url: str) -> None:
    """Promote a prepared package in the local ledger after manual confirmation."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ledger_path = Path(manifest["ledger"])
    fingerprint = manifest["fingerprint"]
    if not ledger_path.is_file():
        raise ValueError("Xiaohongshu publication ledger is missing")

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    record = next(
        (
            item
            for item in ledger.get("records", [])
            if item.get("fingerprint") == fingerprint
        ),
        None,
    )
    if record is None:
        raise ValueError("Xiaohongshu package is missing from the publication ledger")
    record.update(
        {
            "status": "published",
            "external_url": external_url,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    temporary = ledger_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(ledger_path)


def _render_cards(article: ArticlePayload, directory: Path) -> tuple[Path, ...]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for Xiaohongshu cards; install tech-radar[web]"
        ) from exc

    width, height = 1080, 1440
    font_path = _font_path()

    def font(size: int, *, bold: bool = False):
        selected = _font_path(bold=bold) or font_path
        if selected:
            return ImageFont.truetype(str(selected), size)
        return ImageFont.load_default()

    cards: list[Path] = []
    palettes = [
        ("#f2f0e8", "#22231f", "#625ee8"),
        ("#e9eeea", "#20352d", "#2f8969"),
        ("#eeebf5", "#2e2940", "#8a67c7"),
    ]
    sections = _headings(article.body_markdown)
    payloads = [
        (article.topic, article.title, "TECH RADAR · INCREMENTAL BRIEF"),
        ("核心线索", "\n".join(f"{index + 1}. {value}" for index, value in enumerate(sections[:5])), "EVIDENCE FIRST"),
        ("编辑检查", "补充源码与 benchmark\n合并重复事件\n人工检查事实与平台文案", "READY FOR REVIEW"),
    ]
    for index, ((background, ink, accent), payload) in enumerate(
        zip(palettes, payloads, strict=True), start=1
    ):
        image = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (68, 68, width - 68, height - 68),
            radius=42,
            outline=accent,
            width=4,
        )
        draw.rounded_rectangle((88, 92, 212, 132), radius=18, fill=accent)
        draw.text((113, 99), f"0{index}", font=font(25, bold=True), fill="#ffffff")
        draw.text((88, 188), payload[0], font=font(38, bold=True), fill=accent)
        body_font = font(66 if index == 1 else 48, bold=True)
        wrapped = _wrap_pixels(draw, payload[1], body_font, width - 190)
        draw.multiline_text((88, 286), wrapped, font=body_font, fill=ink, spacing=22)
        draw.line((88, height - 210, width - 88, height - 210), fill=accent, width=3)
        draw.text((88, height - 170), payload[2], font=font(25), fill=ink)
        draw.text(
            (88, height - 125),
            "tech-radar / manual review",
            font=font(22),
            fill=accent,
        )
        path = directory / f"{index:02d}.png"
        image.save(path, "PNG", optimize=True)
        cards.append(path)
    return tuple(cards)


def _font_path(*, bold: bool = False) -> Path | None:
    candidates = [
        Path(
            "/mnt/c/Windows/Fonts/msyhbd.ttc"
            if bold
            else "/mnt/c/Windows/Fonts/msyh.ttc"
        ),
        Path(
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
            if bold
            else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
        ),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    return next((path for path in candidates if path.is_file()), None)


def _wrap_pixels(draw: Any, value: str, font: Any, width: int) -> str:
    lines: list[str] = []
    for paragraph in value.splitlines() or [value]:
        ascii_ratio = sum(ord(character) < 128 for character in paragraph) / max(
            len(paragraph), 1
        )
        separator = " " if ascii_ratio > 0.75 else ""
        units = paragraph.split() if separator else list(paragraph)
        current = ""
        for unit in units:
            candidate = separator.join(filter(None, (current, unit)))
            if current and draw.textbbox((0, 0), candidate, font=font)[2] > width:
                lines.append(current)
                current = unit
            else:
                current = candidate
        lines.append(current)
    return "\n".join(lines[:12])


def _xiaohongshu_body(article: ArticlePayload, tags: list[str]) -> str:
    del tags
    text = re.sub(r"```.*?```", "", article.body_markdown, flags=re.DOTALL)
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > 850:
        text = text[:847].rstrip() + "…"
    return text


def _tags(topic: str) -> list[str]:
    values = [topic.replace("/", ""), "技术分享", "开源项目"]
    return list(dict.fromkeys(value.strip().lstrip("#") for value in values if value.strip()))


def _validate_xiaohongshu(title: str, body: str, tags: list[str]) -> None:
    if _weighted_length(title) > 38:
        raise ValueError("Xiaohongshu title exceeds 38 weighted units")
    final_body = f"{body}\n\n" + " ".join(f"#{tag}" for tag in tags)
    if len(final_body) > 1000:
        raise ValueError("Xiaohongshu content exceeds 1000 characters")
    if not 1 <= len(tags) <= 10:
        raise ValueError("Xiaohongshu requires 1-10 tags")


def _truncate_weighted(value: str, limit: int) -> str:
    result = ""
    for character in value:
        if _weighted_length(result + character) > limit:
            break
        result += character
    return result.rstrip(" ：:，,")


def _weighted_length(value: str) -> int:
    return sum(1 if ord(character) < 128 else 2 for character in value)


def _headings(markdown: str) -> list[str]:
    headings = [
        match.group(1).strip()
        for match in re.finditer(r"^###?\s+(?:\d+\.\s*)?(.+)$", markdown, re.MULTILINE)
    ]
    return headings or [line for line in textwrap.wrap(markdown, 36) if line][:5]


def _package_fingerprint(
    title: str,
    body: str,
    tags: list[str],
    source: Path,
    images: tuple[Path, ...],
) -> str:
    payload = {
        "title": title,
        "body": body,
        "tags": tags,
        "source": _file_hash(source),
        "images": [_file_hash(path) for path in images],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_ledger(
    ledger_path: Path, fingerprint: str, manifest_path: Path, status: str
) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = (
        json.loads(ledger_path.read_text(encoding="utf-8"))
        if ledger_path.is_file()
        else {"version": 1, "records": []}
    )
    existing = next(
        (record for record in ledger["records"] if record["fingerprint"] == fingerprint),
        None,
    )
    if existing and existing.get("status") == "published":
        raise ValueError("identical Xiaohongshu package is already published")
    record = existing or {"fingerprint": fingerprint}
    record.update({"manifest": str(manifest_path.resolve()), "status": status})
    if existing is None:
        ledger["records"].append(record)
    temporary = ledger_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(ledger_path)


def _preview_document(title: str, body: str, subtitle: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(title)} · Preview</title>
<style>
body{{margin:0;background:#ece9e1;color:#25251f;font:15px/1.7 system-ui,sans-serif}}
main{{max-width:920px;margin:32px auto;padding:28px;background:#faf9f5;border-radius:18px}}
header{{border-bottom:1px solid #ddd9cf;margin-bottom:24px}}h1{{font:500 32px Georgia,serif;margin:0}}
header p{{color:#766f65}}.markdown{{white-space:pre-wrap;font:14px/1.75 ui-monospace,monospace}}
.phone{{max-width:560px;margin:auto}}.cards{{display:flex;gap:12px;overflow:auto;padding-bottom:12px}}
.cards img{{width:240px;border-radius:14px;box-shadow:0 8px 24px #0002}}.phone h2{{font-size:22px}}
.phone p{{white-space:normal}}.tags{{color:#5d5ce2;margin-top:18px}}
</style></head><body><main><header><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></header>{body}</main></body></html>"""
