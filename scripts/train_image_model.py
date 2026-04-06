"""
Improved YOLOv8 image classification training script.

Changes from original:
  - 100 epochs (was 30) for better convergence
  - 320px images (was 224) for more detail
  - Data augmentation enabled
  - Patience for early stopping
  - Better optimizer settings
"""

from ultralytics import YOLO
from pathlib import Path
import os
import sys

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

DATASET_PATH = str(PROJECT_ROOT / "image_dataset")
MODEL_NAME = str(PROJECT_ROOT / "models" / "yolov8n-cls.pt")
EPOCHS = 100
IMG_SIZE = 320

def check_dataset():
    """Verify dataset structure before training."""
    ds = Path(DATASET_PATH)
    if not ds.exists():
        print(f"❌ Dataset directory '{DATASET_PATH}' not found!")
        sys.exit(1)

    train_dir = ds / "train"
    if not train_dir.exists():
        print("❌ No 'train' directory found in dataset!")
        sys.exit(1)

    print("\n📊 Dataset Summary:")
    print("-" * 40)
    total = 0
    for split in ["train", "valid", "test"]:
        split_dir = ds / split
        if split_dir.exists():
            classes = sorted([d.name for d in split_dir.iterdir() if d.is_dir()])
            split_total = 0
            print(f"\n  {split.upper()}:")
            for cls in classes:
                count = len(list((split_dir / cls).glob("*")))
                split_total += count
                balance = "⚠️ LOW" if count < 50 else "✅"
                print(f"    {cls:30s} {count:5d} images  {balance}")
            total += split_total
            print(f"    {'TOTAL':30s} {split_total:5d}")

    print(f"\n  Grand total: {total} images")
    print("-" * 40)

    # Check for missing classes
    expected = {"pothole", "garbage_dump", "waterlogging", "streetlight_failure", "sewage_overflow"}
    actual = set(classes)
    missing = expected - actual
    if missing:
        print(f"\n⚠️  Missing classes: {missing}")
        print("   Add images for these classes to improve accuracy!")
    print()


def train_image_model():
    check_dataset()

    model = YOLO(MODEL_NAME)

    model.train(
        data=DATASET_PATH,
        epochs=EPOCHS,
        imgsz=IMG_SIZE,

        # Better training settings
        patience=20,           # Early stopping after 20 epochs without improvement
        batch=16,              # Batch size
        lr0=0.001,             # Initial learning rate
        lrf=0.01,              # Final learning rate factor
        weight_decay=0.0005,   # L2 regularization

        # Data augmentation
        augment=True,
        hsv_h=0.015,           # Hue augmentation
        hsv_s=0.7,             # Saturation augmentation
        hsv_v=0.4,             # Value/brightness augmentation
        degrees=15.0,          # Rotation
        translate=0.1,         # Translation
        scale=0.5,             # Scaling
        fliplr=0.5,            # Horizontal flip
        flipud=0.0,            # No vertical flip (civic images don't flip vertically)
        erasing=0.3,           # Random erasing (occlusion simulation)

        # Output
        project="runs",
        name="classify/train",
        exist_ok=True,
        verbose=True,
    )

    print("\n✅ YOLOv8 image classification training completed!")
    print("   Model saved to: runs/classify/train/weights/best.pt")


if __name__ == "__main__":
    train_image_model()
