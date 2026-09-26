"""Normalización de fotos: toda imagen subida termina con la misma medida.

- Acepta JPG, PNG, WEBP, HEIC/HEIF (fotos de iPhone), GIF, BMP, TIFF.
- Corrige la orientación EXIF (fotos giradas del celular).
- Dos modos:
    cover   -> rellena el marco y recorta al centro (sin bordes, para grilla pareja)
    contain -> encaja completa y rellena con fondo claro (no pierde nada de la prenda)
- Genera la imagen principal (por defecto 1200x1600, 3:4) y una miniatura (600x800).
- Guarda el original tal cual llegó, para poder re-procesar más adelante.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

try:  # HEIC de iPhone
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pass

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".tif", ".tiff"}
PAD_COLOR = (247, 243, 240)  # crema muy claro, combina con el fondo del sitio
MAX_PIXELS = 60_000_000      # una foto de 60 MP ya es absurda: corta las bombas de descompresión

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def _open(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    im.verify()                       # descarta archivos que solo dicen ser imágenes
    im = Image.open(io.BytesIO(data))  # verify() deja el archivo consumido: se reabre
    if im.width * im.height > MAX_PIXELS:
        raise ValueError("La imagen es demasiado grande. Mandala en menos resolución.")
    im = ImageOps.exif_transpose(im)  # respeta la orientación de la cámara
    if im.mode in ("RGBA", "LA", "P"):
        # fondo claro debajo de transparencias
        base = Image.new("RGB", im.size, PAD_COLOR)
        im = im.convert("RGBA")
        base.paste(im, mask=im.split()[-1])
        return base
    return im.convert("RGB")


AUTO_TOLERANCE = 0.12  # hasta 12% de diferencia con 3:4 se recorta; más que eso, entra entera


def normalize(im: Image.Image, width: int, height: int, mode: str = "auto") -> Image.Image:
    """Toda foto sale exactamente de width×height, venga como venga.

    auto    -> si la foto ya es casi vertical 3:4 se ajusta al marco; si es cuadrada o
               apaisada (lo típico de las fotos hechas con IA) entra entera sobre un fondo
               hecho con la misma foto desenfocada, así no se corta la prenda
    cover   -> llena el marco recortando al centro
    contain -> entra entera sobre el fondo desenfocado
    """
    if mode == "auto":
        target = width / height
        mode = "cover" if abs(im.width / im.height - target) / target <= AUTO_TOLERANCE else "contain"
    if mode == "contain":
        # fondo: la misma foto llenando el marco, muy desenfocada y un poco aclarada
        bg = ImageOps.fit(im, (width // 4, height // 4), Image.BILINEAR)
        bg = bg.filter(ImageFilter.GaussianBlur(12)).resize((width, height), Image.BILINEAR)
        bg = Image.blend(bg, Image.new("RGB", (width, height), PAD_COLOR), 0.25)
        fitted = ImageOps.contain(im, (width, height), Image.LANCZOS)
        bg.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
        return bg
    return ImageOps.fit(im, (width, height), Image.LANCZOS, centering=(0.5, 0.45))


def process_upload(
    data: bytes,
    original_name: str,
    product_dir: Path,
    originals_dir: Path,
    width: int = 1200,
    height: int = 1600,
    mode: str = "auto",
) -> dict:
    """Guarda original + normalizada + thumb. Devuelve nombres de archivo relativos."""
    ext = Path(original_name).suffix.lower() or ".jpg"
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Formato no soportado: {ext}")
    product_dir.mkdir(parents=True, exist_ok=True)
    originals_dir.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex[:12]
    original_path = originals_dir / f"{uid}{ext}"
    original_path.write_bytes(data)

    im = _open(data)
    main = normalize(im, width, height, mode)
    thumb = main.resize((width // 2, height // 2), Image.LANCZOS)

    main_name = f"{uid}.jpg"
    thumb_name = f"{uid}_thumb.jpg"
    main.save(product_dir / main_name, "JPEG", quality=88, optimize=True, progressive=True)
    thumb.save(product_dir / thumb_name, "JPEG", quality=84, optimize=True, progressive=True)
    return {
        "filename": main_name,
        "thumb": thumb_name,
        "original": original_path.name,
        "width": width,
        "height": height,
        "source_size": im.size,
    }


def reprocess(original_path: Path, product_dir: Path, width: int, height: int, mode: str, main_name: str, thumb_name: str) -> None:
    """Vuelve a generar main+thumb desde el original (cambio de modo o medida)."""
    im = _open(original_path.read_bytes())
    main = normalize(im, width, height, mode)
    main.save(product_dir / main_name, "JPEG", quality=88, optimize=True, progressive=True)
    main.resize((width // 2, height // 2), Image.LANCZOS).save(product_dir / thumb_name, "JPEG", quality=84, optimize=True, progressive=True)


def process_slide(data: bytes, original_name: str, out_dir: Path, originals_dir: Path,
                  size: tuple[int, int], mobile_size: tuple[int, int] | None = None) -> dict:
    """Fotos de portada. El slider tiene dos recortes de la misma foto: uno apaisado para
    la compu y uno vertical para el celular, así la persona no queda cortada en ninguno."""
    ext = Path(original_name).suffix.lower() or ".jpg"
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Formato no soportado: {ext}")
    out_dir.mkdir(parents=True, exist_ok=True)
    originals_dir.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex[:12]
    (originals_dir / f"{uid}{ext}").write_bytes(data)
    im = _open(data)
    name = f"{uid}.jpg"
    ImageOps.fit(im, size, Image.LANCZOS, centering=(0.5, 0.4)).save(out_dir / name, "JPEG", quality=86, optimize=True, progressive=True)
    mobile = None
    if mobile_size:
        mobile = f"{uid}_m.jpg"
        ImageOps.fit(im, mobile_size, Image.LANCZOS, centering=(0.5, 0.4)).save(out_dir / mobile, "JPEG", quality=84, optimize=True, progressive=True)
    return {"filename": name, "mobile": mobile, "original": f"{uid}{ext}"}


def process_logo(data: bytes, original_name: str, out_dir: Path) -> str:
    """El logo conserva la transparencia (PNG) y solo se limita de tamaño."""
    ext = Path(original_name).suffix.lower() or ".png"
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Formato no soportado: {ext}")
    out_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(io.BytesIO(data))
    im.verify()
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    im = im.convert("RGBA")
    im = ImageOps.contain(im, (900, 300), Image.LANCZOS)
    name = f"logo_{uuid.uuid4().hex[:8]}.png"
    im.save(out_dir / name, "PNG", optimize=True)
    # ícono cuadrado para la pestaña del navegador: el logo entero centrado, sin recortar
    icon = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    fit = ImageOps.contain(im, (240, 240), Image.LANCZOS)
    icon.paste(fit, ((256 - fit.width) // 2, (256 - fit.height) // 2), fit)
    icon.save(out_dir / name.replace("logo_", "icon_"), "PNG", optimize=True)
    return name
