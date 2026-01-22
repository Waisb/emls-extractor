import os
import re
import sys
from pathlib import Path
from email import policy
from email.parser import BytesParser

def sanitize_filename(name: str, fallback: str = "attachment.bin") -> str:
    name = (name or "").strip()
    if not name:
        return fallback

    # убираем путь и опасные символы
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[<>:\"/\\|?*\x00-\x1F]", "_", name)
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    return name or fallback

def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 2
    while True:
        candidate = path.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1

def extract_from_eml(eml_path: Path, out_base: Path, per_email_folder: bool = True) -> int:
    with eml_path.open("rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    # подпапка на письмо (по имени файла .eml)
    out_dir = out_base / eml_path.stem if per_email_folder else out_base
    out_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    idx = 0

    # walk по всем частям письма
    for part in msg.walk():
        if part.is_multipart():
            continue

        filename = part.get_filename()
        content_disposition = (part.get_content_disposition() or "").lower()

        # Вложение disposition=attachment
        # встречается inline, но с filename - сохраняем
        is_attachment = (content_disposition == "attachment") or (filename is not None)

        if not is_attachment:
            continue

        idx += 1

        # если имени нет - попробуем расширение по типу
        if not filename:
            maintype = part.get_content_maintype()
            subtype = part.get_content_subtype()
            # fallback
            ext = f".{subtype}" if maintype in ("image", "audio", "video") else ".bin"
            filename = f"attachment_{idx}{ext}"

        filename = sanitize_filename(filename, fallback=f"attachment_{idx}.bin")

        payload = part.get_payload(decode=True)
        if payload is None:
            continue

        out_path = unique_path(out_dir / filename)
        out_path.write_bytes(payload)
        saved += 1

    return saved

def iter_eml_files(root: Path):
    for p in root.rglob("*.eml"):
        if p.is_file():
            yield p

def main():
    if len(sys.argv) < 3:
        print("Использование: python extract_attachments.py <папка_с_eml> <папка_для_сохранения> [--flat]")
        print("  --flat  = не создавать подпапку на каждое письмо, всё в одну папку")
        sys.exit(1)

    eml_dir = Path(sys.argv[1]).expanduser().resolve()
    out_dir = Path(sys.argv[2]).expanduser().resolve()
    flat = "--flat" in sys.argv[3:]

    if not eml_dir.exists():
        print(f"Нет такой папки: {eml_dir}")
        sys.exit(2)

    out_dir.mkdir(parents=True, exist_ok=True)

    total_eml = 0
    total_files = 0

    for eml_path in iter_eml_files(eml_dir):
        total_eml += 1
        try:
            saved = extract_from_eml(eml_path, out_dir, per_email_folder=not flat)
            total_files += saved
            if saved:
                print(f"[OK] {eml_path.name}: сохранено {saved}")
        except Exception as e:
            print(f"[ERR] {eml_path}: {e}")

    print(f"\nГотово. Писем: {total_eml}, вложений сохранено: {total_files}")
    print(f"Папка: {out_dir}")

if __name__ == "__main__":
    main()
