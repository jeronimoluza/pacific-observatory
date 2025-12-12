"""Train a BERT model to classify products to COICOP categories.

This module trains a pretrained BERT model to predict COICOP codes and titles
from product names (product_w_cat).

Workflow:
1. Load and combine classification.csv and mis_classed1.csv
2. Create train/test/validation splits
3. Fine-tune pretrained BERT model
4. Evaluate on train, test, and validation sets
5. Report accuracy metrics
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import unicodedata
import re
import json
from datetime import datetime

import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')


class ProductCoicopsDataset(Dataset):
    """PyTorch Dataset for product-to-COICOP classification."""
    
    def __init__(self, texts: List[str], labels: List[int], tokenizer, max_length: int = 128):
        """
        Args:
            texts: List of product names
            labels: List of label indices
            tokenizer: BERT tokenizer
            max_length: Maximum sequence length
        """
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'labels': torch.tensor(label, dtype=torch.long)
        }


def load_and_combine_data(
    classification_path: Path
) -> pd.DataFrame:
    """
    Load training data from full_classification.csv.
    
    Args:
        classification_path: Path to full_classification.csv
        
    Returns:
        DataFrame with product_w_cat, code, and title columns
    """
    print("Loading training data...")
    df = pd.read_csv(classification_path)
    
    # Keep only required columns and remove duplicates
    df = df[['product_w_cat', 'code', 'title']].drop_duplicates()
    
    print(f"✓ Loaded {len(df)} unique samples from {classification_path.name}")
    
    return df


def create_label_encoders(df: pd.DataFrame) -> Tuple[LabelEncoder, LabelEncoder, Dict, Dict]:
    """
    Create label encoders for codes and titles.
    
    Args:
        df: DataFrame with code and title columns
        
    Returns:
        Tuple of (code_encoder, title_encoder, code_to_idx, title_to_idx)
    """
    code_encoder = LabelEncoder()
    title_encoder = LabelEncoder()
    
    code_encoder.fit(df['code'].unique())
    title_encoder.fit(df['title'].unique())
    
    code_to_idx = {code: idx for idx, code in enumerate(code_encoder.classes_)}
    title_to_idx = {title: idx for idx, title in enumerate(title_encoder.classes_)}
    
    print(f"✓ Created encoders: {len(code_to_idx)} unique codes, {len(title_to_idx)} unique titles")
    
    return code_encoder, title_encoder, code_to_idx, title_to_idx


def split_data(
    df: pd.DataFrame,
    train_ratio: float = 0.7,
    test_ratio: float = 0.15,
    val_ratio: float = 0.15,
    random_state: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split data into train, test, and validation sets.
    
    Args:
        df: DataFrame to split
        train_ratio: Proportion for training (default 0.7)
        test_ratio: Proportion for testing (default 0.15)
        val_ratio: Proportion for validation (default 0.15)
        random_state: Random seed
        
    Returns:
        Tuple of (train_df, test_df, val_df)
    """
    # First split: train + test vs validation
    train_test_df, val_df = train_test_split(
        df,
        test_size=val_ratio,
        random_state=random_state
    )
    
    # Second split: train vs test
    train_df, test_df = train_test_split(
        train_test_df,
        test_size=test_ratio / (train_ratio + test_ratio),
        random_state=random_state
    )
    
    print(f"✓ Data split:")
    print(f"  - Train: {len(train_df)} samples ({len(train_df)/len(df)*100:.1f}%)")
    print(f"  - Test: {len(test_df)} samples ({len(test_df)/len(df)*100:.1f}%)")
    print(f"  - Validation: {len(val_df)} samples ({len(val_df)/len(df)*100:.1f}%)")
    
    return train_df, test_df, val_df


def compute_metrics(eval_pred):
    """Compute accuracy metric for evaluation."""
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    return {'accuracy': accuracy_score(labels, predictions)}


def train_bert_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    val_df: pd.DataFrame,
    code_to_idx: Dict,
    title_to_idx: Dict,
    model_name: str = "bert-base-uncased",
    num_epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    output_dir: str = "./bert_coicop_model"
) -> Tuple[AutoModelForSequenceClassification, AutoTokenizer, Dict]:
    """
    Train BERT model for code prediction.
    
    Args:
        train_df: Training data
        test_df: Test data
        val_df: Validation data
        code_to_idx: Code to index mapping
        title_to_idx: Title to index mapping
        model_name: Pretrained model name
        num_epochs: Number of training epochs
        batch_size: Batch size
        learning_rate: Learning rate
        output_dir: Output directory for model
        
    Returns:
        Tuple of (model, tokenizer, results_dict)
    """
    print(f"\nTraining BERT model ({model_name})...")
    
    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    num_labels = len(code_to_idx)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=num_labels
    )
    
    # Prepare datasets
    train_texts = train_df['product_w_cat'].tolist()
    train_labels = [code_to_idx[code] for code in train_df['code']]
    
    test_texts = test_df['product_w_cat'].tolist()
    test_labels = [code_to_idx[code] for code in test_df['code']]
    
    val_texts = val_df['product_w_cat'].tolist()
    val_labels = [code_to_idx[code] for code in val_df['code']]
    
    train_dataset = ProductCoicopsDataset(train_texts, train_labels, tokenizer)
    test_dataset = ProductCoicopsDataset(test_texts, test_labels, tokenizer)
    val_dataset = ProductCoicopsDataset(val_texts, val_labels, tokenizer)
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        logging_steps=50,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_accuracy",
        push_to_hub=False,
        seed=42
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics
    )
    
    # Train
    print("Starting training...")
    trainer.train()
    
    # Evaluate on all sets
    print("\nEvaluating model...")
    
    train_predictions = trainer.predict(train_dataset)
    train_preds = np.argmax(train_predictions.predictions, axis=1)
    train_accuracy = np.mean(train_preds == np.array(train_labels))
    
    test_predictions = trainer.predict(test_dataset)
    test_preds = np.argmax(test_predictions.predictions, axis=1)
    test_accuracy = np.mean(test_preds == np.array(test_labels))
    
    val_predictions = trainer.predict(val_dataset)
    val_preds = np.argmax(val_predictions.predictions, axis=1)
    val_accuracy = np.mean(val_preds == np.array(val_labels))
    
    results = {
        'train_accuracy': float(train_accuracy),
        'test_accuracy': float(test_accuracy),
        'val_accuracy': float(val_accuracy),
        'num_labels': num_labels,
        'train_samples': len(train_df),
        'test_samples': len(test_df),
        'val_samples': len(val_df),
        'model_name': model_name,
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"\n✓ Training complete!")
    print(f"  - Train Accuracy: {train_accuracy:.4f}")
    print(f"  - Test Accuracy: {test_accuracy:.4f}")
    print(f"  - Validation Accuracy: {val_accuracy:.4f}")
    
    return model, tokenizer, results


def save_results(
    results: Dict,
    code_to_idx: Dict,
    title_to_idx: Dict,
    output_dir: str = "./bert_coicop_model"
) -> None:
    """
    Save results and mappings to JSON files.
    
    Args:
        results: Results dictionary
        code_to_idx: Code to index mapping
        title_to_idx: Title to index mapping
        output_dir: Output directory
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save results
    results_file = output_path / "training_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✓ Results saved to {results_file}")
    
    # Save mappings
    mappings = {
        'code_to_idx': code_to_idx,
        'title_to_idx': title_to_idx,
        'idx_to_code': {str(v): k for k, v in code_to_idx.items()},
        'idx_to_title': {str(v): k for k, v in title_to_idx.items()}
    }
    mappings_file = output_path / "label_mappings.json"
    with open(mappings_file, 'w') as f:
        json.dump(mappings, f, indent=2)
    print(f"✓ Mappings saved to {mappings_file}")


def run_bert_training(
    classification_path: Optional[Path] = None,
    num_epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    output_dir: str = "./bert_coicop_model"
) -> Dict:
    """
    Main function to run BERT training pipeline.
    
    Args:
        classification_path: Path to full_classification.csv
        num_epochs: Number of training epochs
        batch_size: Batch size
        learning_rate: Learning rate
        output_dir: Output directory for model
        
    Returns:
        Dictionary with training results
    """
    # Default path
    if classification_path is None:
        classification_path = Path("full_classification.csv")
    
    # Load data
    df = load_and_combine_data(classification_path)
    
    # Create label encoders
    code_encoder, title_encoder, code_to_idx, title_to_idx = create_label_encoders(df)
    
    # Split data
    train_df, test_df, val_df = split_data(df)
    
    # Train model
    model, tokenizer, results = train_bert_model(
        train_df, test_df, val_df,
        code_to_idx, title_to_idx,
        num_epochs=num_epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        output_dir=output_dir
    )
    
    # Save results
    save_results(results, code_to_idx, title_to_idx, output_dir)
    
    return results


if __name__ == "__main__":
    # Run BERT training
    results = run_bert_training(
        classification_path=Path("full_classification.csv"),
        num_epochs=5,
        batch_size=16,
        learning_rate=2e-5,
        output_dir="./bert_coicop_model"
    )
    
    print("\n" + "="*60)
    print("BERT TRAINING SUMMARY")
    print("="*60)
    print(f"Train Accuracy:      {results['train_accuracy']:.4f}")
    print(f"Test Accuracy:       {results['test_accuracy']:.4f}")
    print(f"Validation Accuracy: {results['val_accuracy']:.4f}")
    print(f"Number of Labels:    {results['num_labels']}")
    print(f"Train Samples:       {results['train_samples']}")
    print(f"Test Samples:        {results['test_samples']}")
    print(f"Val Samples:         {results['val_samples']}")
    print("="*60)
