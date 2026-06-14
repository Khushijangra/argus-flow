import pytest
import numpy as np
from ai.anomaly.ml_anomaly_detector import MLAnomalyDetector

def test_fit_and_detect():
    detector = MLAnomalyDetector(n_features=15, buffer_size=1000, device="cpu")
    
    # Generate mock normal data
    normal_data = np.random.normal(50, 10, size=(150, 15)).astype(np.float32)
    
    # Fit the detector
    metrics = detector.fit(normal_data, ae_epochs=2)
    assert "isolation_forest" in metrics
    assert "autoencoder" in metrics
    
    # Test with normal point - should return None or low score
    normal_point = np.full((15,), 50.0).astype(np.float32)
    alert = detector.detect(normal_point)
    assert alert is None
    
    # Test with clear anomaly
    anomaly_point = np.zeros(15, dtype=np.float32)
    anomaly_point[0] = 999.0 # Extreme outlier
    
    alert = detector.detect(anomaly_point)
    assert alert is not None
    assert alert.severity in ["MEDIUM", "HIGH", "CRITICAL"]
    assert len(alert.detectors_fired) > 0

def test_ensemble_voting():
    detector = MLAnomalyDetector(n_features=15, device="cpu")
    normal_data = np.random.normal(50, 10, size=(150, 15)).astype(np.float32)
    detector.fit(normal_data, ae_epochs=2)
    
    # Extreme anomaly should trigger multiple detectors
    extreme_anomaly = np.ones(15, dtype=np.float32) * 5000.0
    alert = detector.detect(extreme_anomaly)
    
    assert alert is not None
    assert len(alert.detectors_fired) >= 2
    assert alert.severity in ["HIGH", "CRITICAL"]
