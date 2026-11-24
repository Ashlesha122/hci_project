"""
train_test.py
-------------
Training & Testing module for the emotion detection model.
Uses TensorFlow/Keras CNN on the FER-2013 dataset structure.
Provides both training and evaluation functionality.
"""

from __future__ import annotations

import os
import json
import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
DATASET_DIR = os.path.join(BASE_DIR, "dataset")

EMOTION_LABELS = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
IMG_SIZE = 48


def _get_model_path():
    os.makedirs(MODEL_DIR, exist_ok=True)
    return os.path.join(MODEL_DIR, "emotion_model.keras")


def build_cnn_model():
    """Build a simple CNN for emotion classification."""
    from tensorflow import keras
    from tensorflow.keras import layers

    model = keras.Sequential([
        keras.Input(shape=(IMG_SIZE, IMG_SIZE, 1)),
        # Block 1
        layers.Conv2D(32, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.Conv2D(32, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        # Block 2
        layers.Conv2D(64, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.Conv2D(64, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        # Block 3
        layers.Conv2D(128, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        # Dense layers
        layers.Flatten(),
        layers.Dense(256, activation="relu"),
        layers.BatchNormalization(),
        layers.Dropout(0.5),
        layers.Dense(len(EMOTION_LABELS), activation="softmax"),
    ])

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.0001),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _load_dataset_from_folder(folder_path: str):
    """Load images from a folder organized as: folder/emotion_name/*.png"""
    import cv2
    images, labels = [], []

    if not os.path.exists(folder_path):
        return np.array([]), np.array([])

    for label_idx, emotion in enumerate(EMOTION_LABELS):
        emotion_dir = os.path.join(folder_path, emotion)
        if not os.path.isdir(emotion_dir):
            continue
        for img_name in os.listdir(emotion_dir):
            img_path = os.path.join(emotion_dir, img_name)
            try:
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img = cv2.resize(img, (IMG_SIZE, IMG_SIZE))
                images.append(img)
                labels.append(label_idx)
            except Exception:
                continue

    if not images:
        return np.array([]), np.array([])

    X = np.array(images, dtype=np.float32).reshape(-1, IMG_SIZE, IMG_SIZE, 1) / 255.0
    y = np.eye(len(EMOTION_LABELS))[np.array(labels)]
    return X, y


def _create_demo_dataset():
    """Create a small demo dataset with synthetic data for demonstration."""
    np.random.seed(42)
    n_samples = 200
    X = np.random.rand(n_samples, IMG_SIZE, IMG_SIZE, 1).astype(np.float32)
    y_indices = np.random.randint(0, len(EMOTION_LABELS), n_samples)
    y = np.eye(len(EMOTION_LABELS))[y_indices]
    return X, y


def train_model(epochs: int = 10, use_demo: bool = False) -> dict:
    """
    Train the emotion model.
    If dataset/train folder exists, uses real data. Otherwise uses demo data.
    Returns training metrics.
    """
    train_dir = os.path.join(DATASET_DIR, "train")

    if os.path.exists(train_dir) and not use_demo:
        X_train, y_train = _load_dataset_from_folder(train_dir)
        if X_train.size == 0:
            X_train, y_train = _create_demo_dataset()
            data_source = "demo"
        else:
            data_source = "real"
    else:
        X_train, y_train = _create_demo_dataset()
        data_source = "demo"

    model = build_cnn_model()

    # Split for validation
    split = int(0.8 * len(X_train))
    X_tr, X_val = X_train[:split], X_train[split:]
    y_tr, y_val = y_train[:split], y_train[split:]

    history = model.fit(
        X_tr, y_tr,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=32,
        verbose=0,
    )

    # Save model
    model_path = _get_model_path()
    model.save(model_path)

    result = {
        "success": True,
        "data_source": data_source,
        "epochs": epochs,
        "total_samples": len(X_train),
        "train_samples": len(X_tr),
        "val_samples": len(X_val),
        "train_accuracy": round(float(history.history["accuracy"][-1]) * 100, 2),
        "val_accuracy": round(float(history.history["val_accuracy"][-1]) * 100, 2),
        "train_loss": round(float(history.history["loss"][-1]), 4),
        "val_loss": round(float(history.history["val_loss"][-1]), 4),
        "accuracy_history": [round(float(a) * 100, 2) for a in history.history["accuracy"]],
        "val_accuracy_history": [round(float(a) * 100, 2) for a in history.history["val_accuracy"]],
        "loss_history": [round(float(l), 4) for l in history.history["loss"]],
        "val_loss_history": [round(float(l), 4) for l in history.history["val_loss"]],
        "model_path": model_path,
    }
    return result


def test_model(use_demo: bool = False) -> dict:
    """
    Test the trained model.
    If dataset/test folder exists, uses real data. Otherwise uses demo data.
    Returns testing metrics with per-class accuracy.
    """
    model_path = _get_model_path()

    # Support legacy .h5 path if .keras does not exist yet
    if not os.path.exists(model_path):
        legacy_path = os.path.join(MODEL_DIR, "emotion_model.h5")
        if os.path.exists(legacy_path):
            model_path = legacy_path
        else:
            return {"success": False, "error": "No trained model found. Please train the model first."}

    import tensorflow as tf
    model = tf.keras.models.load_model(model_path)
    model.compile(
        optimizer="adam",
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )

    test_dir = os.path.join(DATASET_DIR, "test")

    if os.path.exists(test_dir) and not use_demo:
        X_test, y_test = _load_dataset_from_folder(test_dir)
        if X_test.size == 0:
            X_test, y_test = _create_demo_dataset()
            data_source = "demo"
        else:
            data_source = "real"
    else:
        X_test, y_test = _create_demo_dataset()
        data_source = "demo"

    # Evaluate
    loss, accuracy = model.evaluate(X_test, y_test, verbose=0)

    # Per-class accuracy
    predictions = model.predict(X_test, verbose=0)
    pred_labels = np.argmax(predictions, axis=1)
    true_labels = np.argmax(y_test, axis=1)

    per_class = {}
    for i, emotion in enumerate(EMOTION_LABELS):
        mask = true_labels == i
        if mask.sum() > 0:
            class_acc = float((pred_labels[mask] == i).sum()) / float(mask.sum()) * 100
            per_class[emotion] = round(class_acc, 2)
        else:
            per_class[emotion] = 0.0

    correct = int((pred_labels == true_labels).sum())

    result = {
        "success": True,
        "data_source": data_source,
        "test_accuracy": round(float(accuracy) * 100, 2),
        "test_loss": round(float(loss), 4),
        "total_samples": len(X_test),
        "correct_predictions": correct,
        "per_class_accuracy": per_class,
        "emotion_labels": EMOTION_LABELS,
    }
    return result


def get_model_info() -> dict:
    """Get info about the current model."""
    model_path = _get_model_path()
    legacy_path = os.path.join(MODEL_DIR, "emotion_model.h5")
    exists = os.path.exists(model_path) or os.path.exists(legacy_path)
    active_path = model_path if os.path.exists(model_path) else (legacy_path if os.path.exists(legacy_path) else None)

    dataset_info = {"train": False, "test": False, "train_count": 0, "test_count": 0}
    train_dir = os.path.join(DATASET_DIR, "train")
    test_dir = os.path.join(DATASET_DIR, "test")
    if os.path.exists(train_dir):
        count = sum(len(files) for _, _, files in os.walk(train_dir))
        dataset_info["train"] = count > 0
        dataset_info["train_count"] = count
    if os.path.exists(test_dir):
        count = sum(len(files) for _, _, files in os.walk(test_dir))
        dataset_info["test"] = count > 0
        dataset_info["test_count"] = count

    return {
        "model_exists": exists,
        "model_path": active_path,
        "dataset_info": dataset_info,
        "emotion_labels": EMOTION_LABELS,
    }
