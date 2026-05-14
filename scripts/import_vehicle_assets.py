from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "carrental.settings")

import django

django.setup()

from django.core.files.base import File

from rentals.models import Vehicle, VehicleImage


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


DESKTOP_ROOT = Path.home() / "Desktop" / "RIRI Vehicle Assets"


VEHICLE_ASSETS = [
    {
        "plate_number": "KDR 210A",
        "vehicle_name": "Toyota Corolla Axio",
        "images": [
            {
                "label": "Front exterior",
                "file_title": "File:Toyota Corolla Axio Hybrid (NKE165) front.JPG",
                "license_note": "Wikimedia Commons source page",
                "is_primary": True,
            },
            {
                "label": "Rear exterior",
                "file_title": "File:2006-2008 Toyota Corolla Axio rear.jpg",
                "license_note": "Wikimedia Commons source page",
            },
            {
                "label": "Interior dashboard",
                "file_title": 'File:Toyota COROLLA Axio 1.5G"W×B"2WD (DBA-NRE161-AEXEB(X)) interior.jpg',
                "license_note": "Wikimedia Commons source page",
            },
        ],
    },
    {
        "plate_number": "KDR 211B",
        "vehicle_name": "Toyota Crown",
        "images": [
            {
                "label": "Front exterior",
                "file_title": "File:TOYOTA CROWN (S220).jpg",
                "license_note": "Wikimedia Commons source page",
                "is_primary": True,
            },
            {
                "label": "Rear exterior",
                "file_title": "File:TOYOTA CROWN BACK (S220).jpg",
                "license_note": "Wikimedia Commons source page",
            },
            {
                "label": "Interior dashboard",
                "file_title": "File:2018 Toyota Crown interior.jpg",
                "license_note": "Wikimedia Commons source page",
            },
        ],
    },
    {
        "plate_number": "KDR 212C",
        "vehicle_name": "Nissan X-Trail",
        "images": [
            {
                "label": "Front exterior",
                "file_title": "File:Nissan X-TRAIL 20X (DBA-T32) front.jpg",
                "license_note": "Wikimedia Commons source page",
                "is_primary": True,
            },
            {
                "label": "Rear exterior",
                "file_title": "File:Nissan X-TRAIL 20X (DBA-T32) rear.jpg",
                "license_note": "Wikimedia Commons source page",
            },
            {
                "label": "Interior dashboard",
                "file_title": "File:Nissan X-TRAIL 20X (DBA-T32) interior.jpg",
                "license_note": "Wikimedia Commons source page",
            },
        ],
    },
    {
        "plate_number": "KDR 213D",
        "vehicle_name": "Toyota Harrier",
        "images": [
            {
                "label": "Front exterior",
                "file_title": "File:Toyota HARRIER HYBRID Z 2WD (front).jpg",
                "license_note": "Wikimedia Commons source page",
                "is_primary": True,
            },
            {
                "label": "Rear exterior",
                "file_title": "File:2014 Toyota Harrier (rear).jpg",
                "license_note": "Wikimedia Commons source page",
            },
            {
                "label": "Interior dashboard",
                "file_title": "File:Toyota Harrier U60 interior.jpg",
                "license_note": "Wikimedia Commons source page",
            },
        ],
    },
    {
        "plate_number": "KDR 214E",
        "vehicle_name": "Toyota Land Cruiser Prado",
        "images": [
            {
                "label": "Front exterior",
                "file_title": "File:2013-2017 Toyota Land Cruiser Prado (front).jpg",
                "license_note": "Wikimedia Commons source page",
                "is_primary": True,
            },
            {
                "label": "Rear exterior",
                "file_title": "File:Toyota Land Cruiser Prado TX 2011 (rear).jpg",
                "license_note": "Wikimedia Commons source page",
            },
            {
                "label": "Interior dashboard",
                "file_title": "File:Toyota Land Cruiser Prado 150 interior.jpg",
                "license_note": "Wikimedia Commons source page",
            },
        ],
    },
    {
        "plate_number": "KDR 215F",
        "vehicle_name": "BMW X5",
        "images": [
            {
                "label": "Front exterior",
                "file_title": "File:BMW X5 xDrive35d (G05) front.jpg",
                "license_note": "Wikimedia Commons source page",
                "is_primary": True,
            },
            {
                "label": "Rear exterior",
                "file_title": "File:2019 BMW X5 M50d 3.0 Rear.jpg",
                "license_note": "Wikimedia Commons source page",
            },
            {
                "label": "Interior dashboard",
                "file_title": "File:2020 BMW X5 (G05) interior.jpg",
                "license_note": "Wikimedia Commons source page",
            },
        ],
    },
]


def build_direct_download_url(file_title: str) -> str:
    filename = file_title.removeprefix("File:")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(filename, safe='')}"


def build_page_url(file_title: str) -> str:
    return f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(file_title, safe=':()')}"


def build_thumbnail_download_url(file_title: str, width: int = 1600) -> str:
    filename = file_title.removeprefix("File:").replace(" ", "_")
    digest = hashlib.md5(filename.encode("utf-8")).hexdigest()
    encoded_filename = urllib.parse.quote(filename, safe="")
    return (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/"
        f"{digest[0]}/{digest[:2]}/{encoded_filename}/{width}px-{encoded_filename}"
    )


def download_file(url: str, destination: Path) -> None:
    last_error = None
    for attempt in range(1, 5):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        try:
            with urllib.request.urlopen(request) as response, destination.open("wb") as target:
                shutil.copyfileobj(response, target)
            time.sleep(1.5)
            return
        except Exception as exc:  # pragma: no cover - one-off import script
            last_error = exc
            wait_seconds = 8 * attempt
            time.sleep(wait_seconds)
    raise last_error


def main() -> None:
    DESKTOP_ROOT.mkdir(parents=True, exist_ok=True)
    credits_lines = [
        "# RIRI Vehicle Assets",
        "",
        "Downloaded for local presentation use and wired into the Django gallery.",
        "Each source page below is on Wikimedia Commons. Review the linked page for the exact license details.",
        "",
    ]

    imported_total = 0
    failed_downloads: list[str] = []

    for vehicle_spec in VEHICLE_ASSETS:
        vehicle = Vehicle.objects.get(plate_number=vehicle_spec["plate_number"])
        vehicle_slug = slugify(vehicle_spec["vehicle_name"])
        vehicle_dir = DESKTOP_ROOT / vehicle_slug
        vehicle_dir.mkdir(parents=True, exist_ok=True)
        existing_images = {image.caption: image for image in vehicle.gallery_images.all()}

        credits_lines.append(f"## {vehicle_spec['vehicle_name']}")
        credits_lines.append("")

        for index, image_spec in enumerate(vehicle_spec["images"], start=1):
            direct_url = build_download_url(image_spec["file_title"])
            direct_url = build_thumbnail_download_url(image_spec["file_title"])
            page_url = build_page_url(image_spec["file_title"])
            original_name = image_spec["file_title"].removeprefix("File:")
            extension = Path(original_name).suffix or ".jpg"
            local_name = f"{index:02d}-{slugify(image_spec['label'])}{extension.lower()}"
            local_path = vehicle_dir / local_name

            existing_image = existing_images.get(image_spec["label"])
            if existing_image and existing_image.image:
                existing_image.display_order = index
                existing_image.is_primary = image_spec.get("is_primary", False)
                existing_image.save(update_fields=["display_order", "is_primary"])
                credits_lines.append(f"- **{image_spec['label']}**")
                credits_lines.append(f"  - Desktop file: `{local_name}`")
                credits_lines.append(f"  - Source page: {page_url}")
                credits_lines.append(f"  - Direct download: {direct_url}")
                credits_lines.append(f"  - Notes: {image_spec['license_note']}")
                continue

            try:
                download_file(direct_url, local_path)
            except Exception as exc:  # pragma: no cover - one-off import script
                failed_downloads.append(f"{vehicle_spec['vehicle_name']} - {image_spec['label']}: {exc}")
                continue

            if vehicle.image or vehicle.image_url:
                vehicle.image = None
                vehicle.image_url = ""
                vehicle.save(update_fields=["image", "image_url"])

            with local_path.open("rb") as file_handle:
                gallery_image = existing_image or VehicleImage(vehicle=vehicle, caption=image_spec["label"])
                gallery_image.is_primary = image_spec.get("is_primary", False)
                gallery_image.display_order = index
                gallery_image.image.save(
                    f"{vehicle_slug}-{index:02d}{extension.lower()}",
                    File(file_handle),
                    save=False,
                )
                gallery_image.save()

            credits_lines.append(f"- **{image_spec['label']}**")
            credits_lines.append(f"  - Desktop file: `{local_path.name}`")
            credits_lines.append(f"  - Source page: {page_url}")
            credits_lines.append(f"  - Direct download: {direct_url}")
            credits_lines.append(f"  - Notes: {image_spec['license_note']}")
            imported_total += 1

        credits_lines.append("")

    credits_path = DESKTOP_ROOT / "README-vehicle-image-sources.md"
    credits_path.write_text("\n".join(credits_lines), encoding="utf-8")

    print(f"Imported {imported_total} images into {DESKTOP_ROOT}")
    print(f"Credits file: {credits_path}")
    if failed_downloads:
        print("Failed downloads:")
        for failure in failed_downloads:
            print(f" - {failure}")


if __name__ == "__main__":
    main()
