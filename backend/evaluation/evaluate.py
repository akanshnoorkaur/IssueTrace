from __future__ import annotations
"""
IssueLens Benchmark Evaluation Script

Evaluates triage accuracy, precision, recall, and confusion matrix
against a curated benchmark dataset with reference triage labels.
"""

import json
from pathlib import Path
from collections import defaultdict

DATASET_PATH = Path(__file__).parent / "dataset.json"


def evaluate_predictions(predictions: list[dict], ground_truth: list[dict]):
    """Calculate accuracy, precision, recall, and confusion matrix."""
    labels = ["CONFIRMED", "INVALID", "CANNOT_REPRODUCE"]
    matrix = {actual: {pred: 0 for pred in labels} for actual in labels}
    
    gt_map = {item["id"]: item["reference_label"] for item in ground_truth}
    
    total = 0
    correct = 0
    
    for p in predictions:
        p_id = p["id"]
        pred_label = p["predicted_label"]
        actual_label = gt_map.get(p_id)
        if not actual_label:
            continue
        
        matrix[actual_label][pred_label] += 1
        total += 1
        if pred_label == actual_label:
            correct += 1

    accuracy = correct / total if total > 0 else 0.0

    print("=" * 60)
    print("IssueLens Triage Evaluation Results")
    print("=" * 60)
    print(f"Total benchmark samples: {total}")
    print(f"Overall Accuracy:        {accuracy:.2%}\n")

    print("Confusion Matrix (Rows: Reference Label, Columns: Predicted Label):")
    header = f"{'Actual':<18} | " + " | ".join(f"{l:<16}" for l in labels)
    print(header)
    print("-" * len(header))
    for actual in labels:
        row = f"{actual:<18} | " + " | ".join(f"{matrix[actual][pred]:<16}" for pred in labels)
        print(row)
    print("-" * len(header))

    # Per-class metrics
    print("\nPer-Class Precision & Recall:")
    for l in labels:
        tp = matrix[l][l]
        fp = sum(matrix[other][l] for other in labels if other != l)
        fn = sum(matrix[l][other] for other in labels if other != l)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        print(f"  {l:<18} -> Precision: {precision:.2f}, Recall: {recall:.2f}, F1: {f1:.2f}")
    print("=" * 60)


if __name__ == "__main__":
    with open(DATASET_PATH) as f:
        gt = json.load(f)

    # Simulated predictions for baseline benchmark verification
    sample_preds = [
        {"id": 1, "predicted_label": "CONFIRMED"},
        {"id": 2, "predicted_label": "INVALID"},
        {"id": 3, "predicted_label": "CANNOT_REPRODUCE"},
        {"id": 4, "predicted_label": "CONFIRMED"},
        {"id": 5, "predicted_label": "INVALID"},
    ]
    evaluate_predictions(sample_preds, gt)
