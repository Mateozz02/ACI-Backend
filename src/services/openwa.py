import httpx
from typing import Optional

from src.config import get_settings

settings = get_settings()


class OpenWAService:
    def __init__(self, session_name: str = ""):
        self.base_url = settings.openwa_api_url
        self.api_key = settings.openwa_api_key
        self.session_name = session_name or settings.openwa_session_name

    def _get_headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _get_session(self, session_name: Optional[str] = None) -> str:
        return session_name or self.session_name

    async def send_text(self, phone: str, text: str, session_name: Optional[str] = None) -> dict:
        """Send a text message via WhatsApp"""
        session = self._get_session(session_name)
        url = f"{self.base_url}/api/sessions/{session}/messages/send-text"

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

            if response.status_code not in (200, 201):
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")

            return response.json()

    async def send_image(
        self,
        phone: str,
        image_url: str,
        caption: Optional[str] = None,
        session_name: Optional[str] = None,
    ) -> dict:
        """Send an image via WhatsApp"""
        session = self._get_session(session_name)
        url = f"{self.base_url}/api/sessions/{session}/messages/send-image"

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

            if response.status_code not in (200, 201):
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")

            return response.json()

    async def get_session_status(self, session_name: Optional[str] = None) -> dict:
        """Check if the WhatsApp session is connected"""
        session = self._get_session(session_name)
        url = f"{self.base_url}/api/sessions/{session}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")

            return response.json()

    async def create_session(self, name: str) -> dict:
        url = f"{self.base_url}/api/sessions"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json={"name": name},
                headers=self._get_headers(),
            )
            if response.status_code == 409:
                sessions = await self.list_sessions()
                for s in sessions:
                    if s["name"] == name:
                        return s
                raise Exception("Session exists but not found in list")
            if response.status_code not in (200, 201):
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")
            return response.json()

    async def list_sessions(self) -> list[dict]:
        url = f"{self.base_url}/api/sessions"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=self._get_headers())
            if response.status_code != 200:
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")
            return response.json()
    async def start_session(self, session_name: str) -> dict:
        try:
            s = await self.get_session_status(session_name)
            if s["status"] in ("qr_ready", "ready"):
                return s
        except Exception:
            pass

        url = f"{self.base_url}/api/sessions/{session_name}/start"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=self._get_headers())
            if response.status_code == 400:
                return await self.get_session_status(session_name)
            if response.status_code not in (200, 201):
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")
            return response.json()

    async def get_session_qr(self, session_name: str) -> dict:
        url = f"{self.base_url}/api/sessions/{session_name}/qr"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=self._get_headers())
            if response.status_code != 200:
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")
            return response.json()

    async def delete_session(self, session_name: str) -> dict:
        url = f"{self.base_url}/api/sessions/{session_name}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(url, headers=self._get_headers())
            if response.status_code != 200:
                raise Exception(f"OpenWA error: {response.status_code} - {response.text}")
            return response.json()


openwa_service = OpenWAService()
