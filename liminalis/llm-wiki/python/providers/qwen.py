"""Tongyi Qwen mock provider."""

from python.schemas.domain import PhotoExtraction, Sensitivity


class QwenProvider:
    def __init__(self):
        self.name = "qwen"
        self.model = "qwen-vl-max"

    def extract_photo_context(self, filename: str, metadata: dict | None = None) -> PhotoExtraction:
        return PhotoExtraction(
            text="用户在上海市中心拍摄的街景照片，适合围绕城市漫步、周末活动建立低压力的社交话题。",
            topics=["城市漫步", "周末活动", "上海"],
            sensitivity=Sensitivity.normal,
            confidence=0.93,
            privacy_flags={
                "has_face": False,
                "has_child_risk": False,
                "has_exact_location": False,
                "face_identity_used": False,
                "exact_location_exposed": False,
            },
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        out = []
        for text in texts:
            h = hashlib.sha256(text.encode()).digest()
            vec = [float(b) / 255.0 for b in h[:64]]
            out.append(vec)
        return out
