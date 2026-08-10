"""Doubao (豆包) mock provider."""

from python.schemas.domain import PhotoExtraction, Sensitivity


class DoubaoProvider:
    def __init__(self):
        self.name = "doubao"
        self.model = "doubao-vision-pro"

    def extract_photo_context(self, filename: str, metadata: dict | None = None) -> PhotoExtraction:
        return PhotoExtraction(
            text="照片记录了城市周末生活场景，包含美食和街头文化元素，适合作为轻松社交话题。",
            topics=["美食", "周末生活", "城市探索"],
            sensitivity=Sensitivity.normal,
            confidence=0.91,
            privacy_flags={
                "has_face": False,
                "has_child_risk": False,
                "has_exact_location": False,
                "face_identity_used": False,
                "exact_location_exposed": False,
            },
        )
