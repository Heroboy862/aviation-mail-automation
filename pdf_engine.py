import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


ALLOW_MISSING_TEMPLATE_FALLBACK = _env_flag("ALLOW_MISSING_TEMPLATE_FALLBACK", "true")


def _load_font(font_path: Path, size: int = 44) -> ImageFont.ImageFont:
    """
    Load preferred project font, fallback to default Pillow font if missing.
    """
    if font_path.exists():
        try:
            return ImageFont.truetype(str(font_path), size=size)
        except OSError:
            pass

    return ImageFont.load_default()


def _wrap_text(
    *,
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    words = text.split()
    if not words:
        return ""

    lines: list[str] = []
    current_line = words[0]

    for word in words[1:]:
        candidate = f"{current_line} {word}"
        candidate_width = draw.textlength(candidate, font=font)
        if candidate_width <= max_width:
            current_line = candidate
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)
    return "\n".join(lines)


def _get_qr_overlay() -> tuple[Image.Image, tuple[int, int]] | None:
    """Load optional QR image and target position from env."""
    qr_path_raw = os.getenv("QR_CODE_IMAGE_PATH", "").strip()
    if not qr_path_raw:
        return None

    qr_path = Path(qr_path_raw)
    if not qr_path.exists():
        return None

    try:
        size = max(80, int(os.getenv("QR_CODE_SIZE", "320")))
    except ValueError:
        size = 320

    try:
        qr_image = Image.open(qr_path).convert("RGBA")
    except Exception:
        return None

    qr_image = qr_image.resize((size, size))

    try:
        x = int(os.getenv("QR_CODE_X", "0"))
        y = int(os.getenv("QR_CODE_Y", "0"))
    except ValueError:
        x, y = 0, 0
    return qr_image, (x, y)


def generate_participant_pdf(
    *,
    template_path: Path,
    output_path: Path,
    font_path: Path,
    participant_name: str,
    school_name: str,
    department_name: str,
    career_advice: str,
    text_coords: dict,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    title_font = _load_font(font_path=font_path, size=44)
    advice_title_font = _load_font(font_path=font_path, size=36)
    advice_font = _load_font(font_path=font_path, size=34)

    if template_path.exists():
        image = Image.open(template_path).convert("RGB")
    elif ALLOW_MISSING_TEMPLATE_FALLBACK:
        image = Image.new("RGB", (2480, 3508), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        warn_font = _load_font(font_path=font_path, size=36)
        draw.text(
            xy=(150, 150),
            text=f"Template bulunamadi: {template_path.name}",
            font=warn_font,
            fill=(160, 20, 20),
        )
        draw.text(
            xy=(150, 220),
            text="Gecici fallback cikti olusturuldu.",
            font=warn_font,
            fill=(90, 90, 90),
        )
    else:
        raise FileNotFoundError(f"Template dosyasi bulunamadi: {template_path}")

    with image:
        draw = ImageDraw.Draw(image)

        draw.text(
            xy=text_coords["name"],
            text=participant_name.strip(),
            font=title_font,
            fill=(22, 35, 74),
        )
        draw.text(
            xy=text_coords["school"],
            text=school_name.strip(),
            font=title_font,
            fill=(45, 45, 45),
        )
        draw.text(
            xy=text_coords["department"],
            text=department_name.strip(),
            font=title_font,
            fill=(10, 72, 125),
        )

        advice_x, advice_y = text_coords.get(
            "career_advice",
            (text_coords["name"][0], text_coords["department"][1] + 130),
        )
        draw.text(
            xy=(advice_x, advice_y),
            text="Kariyer Tavsiyesi:",
            font=advice_title_font,
            fill=(18, 48, 98),
        )

        advice_text_y = advice_y + 50
        max_advice_width = int(text_coords.get("career_advice_max_width", image.width - (advice_x * 2)))
        wrapped_advice = _wrap_text(
            draw=draw,
            text=career_advice.strip(),
            font=advice_font,
            max_width=max(max_advice_width, 400),
        )
        if wrapped_advice:
            draw.multiline_text(
                xy=(advice_x, advice_text_y),
                text=wrapped_advice,
                font=advice_font,
                fill=(35, 35, 35),
                spacing=12,
            )

        qr_overlay = _get_qr_overlay()
        if qr_overlay is not None:
            qr_image, (qr_x, qr_y) = qr_overlay
            if qr_x <= 0:
                qr_x = image.width - qr_image.width - 120
            if qr_y <= 0:
                qr_y = image.height - qr_image.height - 120
            image.paste(qr_image, (qr_x, qr_y), qr_image)

        image.save(str(output_path), "PDF", resolution=300.0)

    return output_path
