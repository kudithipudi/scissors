"""QR code generation service."""
import base64
from io import BytesIO

import qrcode
from fastapi import Request

from app.config import settings
from app.templating import build_url


class QRService:
    """Service for generating QR codes."""

    @staticmethod
    def generate_qr_code(request: Request, game_code: str) -> str:
        """
        Generate QR code for game joining.

        Returns:
            Base64 encoded PNG image
        """
        # Build join URL, prefixed with ROOT_PATH so it's reachable through nginx.
        join_url = build_url(request, 'view_game', game_code=game_code)

        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=settings.QR_BOX_SIZE,
            border=settings.QR_BORDER,
        )
        qr.add_data(join_url)
        qr.make(fit=True)

        # Generate image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_base64}"

    @staticmethod
    def get_join_url(request: Request, game_code: str) -> str:
        """Get the join URL for a game code."""
        return build_url(request, 'view_game', game_code=game_code)
