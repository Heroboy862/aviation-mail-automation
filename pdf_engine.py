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


def generate_participant_pdf(
    *,
    template_path: Path,
    output_path: Path,
    font_path: Path,
    participant_name: str,
    school_name: str,
    department_name: str,
    text_coords: dict,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font = _load_font(font_path=font_path, size=44)

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
            font=font,
            fill=(22, 35, 74),
        )
        draw.text(
            xy=text_coords["school"],
            text=school_name.strip(),
            font=font,
            fill=(45, 45, 45),
        )
        draw.text(
            xy=text_coords["department"],
            text=department_name.strip(),
            font=font,
            fill=(10, 72, 125),
        )

        image.save(str(output_path), "PDF", resolution=300.0)

    return output_path
