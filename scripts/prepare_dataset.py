"""
Dataset preparation script for CivicConnect AI image classifier.

This script helps:
1. Create the sewage_overflow class directory (missing from current dataset)
2. Check dataset balance across all classes
3. Provide guidance on collecting more images

Usage:
    python3 prepare_dataset.py
"""

import os
import shutil
from pathlib import Path

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "image_dataset"
REQUIRED_CLASSES = [
    "pothole",
    "garbage_dump",
    "waterlogging",
    "streetlight_failure",
    "sewage_overflow",  # NEW — currently missing
]

MINIMUM_IMAGES = 100  # Recommended minimum per class


def setup_directories():
    """Create missing class directories."""
    print("\n📁 Setting up dataset directories...")
    for split in ["train", "valid", "test"]:
        split_dir = DATASET_PATH / split
        split_dir.mkdir(exist_ok=True)
        for cls in REQUIRED_CLASSES:
            cls_dir = split_dir / cls
            if not cls_dir.exists():
                cls_dir.mkdir(parents=True, exist_ok=True)
                print(f"  ✅ Created: {split}/{cls}/")
            else:
                count = len([f for f in cls_dir.iterdir() if f.is_file()])
                status = "⚠️ NEEDS MORE" if count < MINIMUM_IMAGES else "✅"
                print(f"  {status} {split}/{cls}/ — {count} images")


def print_collection_guide():
    """Print guidance on collecting images."""
    print("\n" + "="*60)
    print("📸 IMAGE COLLECTION GUIDE")
    print("="*60)

    print("""
To improve the model, you need to add images for each class.
Here are recommended sources and tips:

🚰 SEWAGE_OVERFLOW (HIGH PRIORITY — 0 images currently!)
   What to capture:
   ├── Open/broken manhole covers
   ├── Sewage water overflowing onto roads
   ├── Clogged drains with stagnant dirty water
   ├── Manhole covers with water seeping around them
   └── Sewage nala/drain overflow

   Sources:
   ├── Take photos during field inspections
   ├── Roboflow: search "sewage" or "manhole"
   ├── Google Images: "sewage overflow india road"
   └── Kaggle datasets on urban infrastructure

🕳️  POTHOLE (465 images — OK but can be improved)
   Consider adding diverse angles, lighting, sizes

🚿 WATERLOGGING (22 images — VERY LOW!)
   Need at least 80+ more images of flooded roads

💡 STREETLIGHT_FAILURE (43 images — LOW!)
   Need at least 60+ more images

🗑️  GARBAGE_DUMP (152 images — OK)

📋 TIPS FOR BETTER ACCURACY:
   1. Aim for 150-300 images per class (balanced)
   2. Include varied conditions: day/night, rain, close-up/wide
   3. Split: 70% train / 20% valid / 10% test
   4. Remove blurry or ambiguous images
   5. After adding images, delete .cache files and retrain
""")


def cleanup_caches():
    """Remove cache files that may cause issues when dataset changes."""
    for cache in DATASET_PATH.glob("*.cache"):
        cache.unlink()
        print(f"  🗑️  Removed cache: {cache.name}")


if __name__ == "__main__":
    print("🔧 CivicConnect AI — Dataset Preparation Tool")
    print("=" * 50)

    if not DATASET_PATH.exists():
        print(f"❌ Dataset directory not found at: {DATASET_PATH}")
        exit(1)

    setup_directories()
    cleanup_caches()
    print_collection_guide()

    print("\n✅ Done! After adding images, run:")
    print("   python3 train_image_model.py")
    print()
