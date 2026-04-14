from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


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
    if not template_path.exists():
        raise FileNotFoundError(f"Template dosyasi bulunamadi: {template_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    font = _load_font(font_path=font_path, size=44)

    with Image.open(template_path).convert("RGB") as image:
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
