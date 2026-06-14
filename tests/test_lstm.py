import pytest
import numpy as np
import torch
from ai.prediction.lstm_predictor import LSTMPredictor

def test_model_forward():
    # Model configuration
    history_len = 10
    forecast_horizon = 6
    features = 15
    
    predictor = LSTMPredictor(
        history_len=history_len,
        forecast_horizon=forecast_horizon,
        n_features=features,
        device="cpu"
    )
    
    # Needs to be fitted or initialized to evaluate forward pass directly
    # The LSTMPredictor encapsulates the PyTorch module.
    # We will instantiate the internal seq2seq model to test its shapes.
    
    # Ensure predictor builds the internal model
    # Normally done during fit, but we can manually invoke it for testing
    # if it's not exposed, we just train it with 1 epoch on mock data
    
    mock_data = np.random.normal(50, 10, size=(100, features)).astype(np.float32)
    predictor.fit(mock_data, epochs=1, batch_size=16)
    
    assert predictor.model is not None
    
    # Test forward shape
    batch_size = 4
    x = torch.randn(batch_size, history_len, features)
    
    predictor.model.eval()
    with torch.no_grad():
        out = predictor.model(x)
        
    assert out.shape == (batch_size, forecast_horizon, features)
