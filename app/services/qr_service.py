"""QR code generation service."""
import qrcode
from io import BytesIO
import base64
from flask import current_app, request, url_for


class QRService:
    """Service for generating QR codes."""

    @staticmethod
    def generate_qr_code(game_code: str) -> str:
        """
        Generate QR code for game joining.

        Returns:
            Base64 encoded PNG image
        """
        # Build join URL using url_for to respect application root
        join_url = url_for('game.view_game', game_code=game_code, _external=True)

        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=current_app.config['QR_BOX_SIZE'],
            border=current_app.config['QR_BORDER'],
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
    def get_join_url(game_code: str) -> str:
        """Get the join URL for a game code."""
        return url_for('game.view_game', game_code=game_code, _external=True)
