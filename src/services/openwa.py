import httpx
from typing import Optional

from src.config import get_settings

settings = get_settings()


class OpenWAService:
    def __init__(self):
        self.base_url = settings.openwa_api_url
        self.api_key = settings.openwa_api_key
        self.session_name = settings.openwa_session_name

    def _get_headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def send_text(self, phone: str, text: str) -> dict:
        """Send a text message via WhatsApp"""
        url = f"{self.base_url}/api/sessions/{self.session_name}/messages/send-text"

        payload = {
            "chatId": f"{phone}@s.whatsapp.net",
            "text": text,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")

            return response.json()

    async def send_image(
        self,
        phone: str,
        image_url: str,
        caption: Optional[str] = None,
    ) -> dict:
        """Send an image via WhatsApp"""
        url = f"{self.base_url}/api/sessions/{self.session_name}/messages/send-image"

        payload = {
            "chatId": f"{phone}@s.whatsapp.net",
            "image": image_url,
        }

        if caption:
            payload["caption"] = caption

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")

            return response.json()

    async def get_session_status(self) -> dict:
        """Check if the WhatsApp session is connected"""
        url = f"{self.base_url}/api/sessions/{self.session_name}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")

            return response.json()


openwa_service = OpenWAService()
