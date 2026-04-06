"""Train the text classification model on the civic complaints dataset."""

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
from pathlib import Path

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    # 1. Load data
    df = pd.read_csv(PROJECT_ROOT / "data" / "civic_complaint_scripts_1000.csv")

    # Basic cleaning
    df["text"] = df["text"].astype(str).str.lower().str.strip()
    df["label"] = df["label"].astype(str).str.strip()

    print(f"Loaded {len(df)} rows with {df['label'].nunique()} classes")
    print(df["label"].value_counts())
    print()

    # 2. Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        df["text"],
        df["label"],
        test_size=0.20,
        random_state=42,
        stratify=df["label"],
    )

    # 3. ML pipeline — TF-IDF + LinearSVC
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=8000,
            stop_words="english",
            sublinear_tf=True,
        )),
        ("clf", LinearSVC(
            C=1.0,
            max_iter=5000,
        )),
    ])

    # 4. Train
    pipe.fit(X_train, y_train)

    # 5. Evaluate
    y_pred = pipe.predict(X_test)
    print(classification_report(y_test, y_pred))

    # 6. Save model
    models_dir = PROJECT_ROOT / "models"
    models_dir.mkdir(exist_ok=True)
    joblib.dump(pipe, models_dir / "text_model.joblib")

    print("✅ Model saved to models/text_model.joblib")

    # 7. Quick sanity check
    test_complaints = [
        "There is a big pothole on the main road near my house",
        "Garbage is piling up near the bus stop for 3 days",
        "Sewage water is overflowing on the street",
        "Street lights are not working in our colony",
        "Water pipe is leaking near the junction",
        "There is waterlogging after rain in our area",
        "Road is completely damaged with cracks everywhere",
        "Trash and waste dumped openly near park",
        "Drain is blocked and dirty water flowing on road",
        "All the lights on the road are switched off at night",
        "Stray dogs attacking people near school",
        "Flooding in the colony after heavy rain",
        "Manhole is open and sewage leaking on road",
        "Rubbish piled up near market, foul smell",
    ]

    print("\nSanity check predictions:")
    print("=" * 75)
    for text in test_complaints:
        pred = pipe.predict([text])[0]
        print(f"  [{pred:>28}]  {text}")


if __name__ == "__main__":
    main()
