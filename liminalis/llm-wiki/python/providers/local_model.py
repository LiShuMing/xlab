"""Local model mock provider (e.g. Ollama)."""

from python.schemas.domain import PhotoExtraction, Sensitivity


class LocalModelProvider:
    def __init__(self, model_name: str = "llama3.2-vision"):
        self.name = "local"
        self.model = model_name

    def extract_photo_context(self, filename: str, metadata: dict | None = None) -> PhotoExtraction:
        return PhotoExtraction(
            text="日常生活照片，适合围绕共同兴趣和日常活动建立低压力的社交连接。",
            topics=["日常生活", "社交", "兴趣分享"],
            sensitivity=Sensitivity.normal,
            confidence=0.85,
            privacy_flags={
                "has_face": False,
                "has_child_risk": False,
                "has_exact_location": False,
                "face_identity_used": False,
                "exact_location_exposed": False,
            },
        )
