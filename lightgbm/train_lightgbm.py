import lightgbm as lgb
import numpy as np
import os

# Step 1: Generate or load training data
# For this example, we'll use random dummy data
np.random.seed(42)  # Set seed for reproducibility
X_train = np.random.rand(100, 5)  # 100 samples, 5 features
y_train = np.random.randint(0, 2, 100)  # Binary labels (0 or 1)

# Step 2: Prepare data for LightGBM
train_data = lgb.Dataset(X_train, label=y_train)

# Step 3: Set training parameters
params = {
    'objective': 'binary',       # Binary classification
    'metric': 'binary_logloss',  # Loss function for binary classification
    'boosting_type': 'gbdt',     # Gradient Boosting Decision Tree
    'num_leaves': 31,            # Maximum number of leaves in one tree
    'learning_rate': 0.05,       # Learning rate
    'feature_fraction': 0.9      # Fraction of features to consider per split
}

# Step 4: Train the LightGBM model
print("Training LightGBM model...")
model = lgb.train(params, train_data, num_boost_round=100)

# Step 5: Save the trained model
model_dir = "./models"
os.makedirs(model_dir, exist_ok=True)  # Create directory if it doesn't exist
model_path = os.path.join(model_dir, "lightgbm_model.txt")
model.save_model(model_path)
print(f"Model saved to: {model_path}")
