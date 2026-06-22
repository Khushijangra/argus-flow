import zmq
import json
import logging
import time

class VisionBridge:
    """
    Acts as the ZeroMQ client to poll the isolated ARGUS Inference Server.
    Provides timeout protection to ensure the RL simulation never hangs.
    """
    def __init__(self, port=5555, timeout_ms=50):
        self.port = port
        self.timeout_ms = timeout_ms
        self.context = zmq.Context()
        self.socket = None
        self.poller = zmq.Poller()
        self._connect()
        
    def _connect(self):
        if self.socket:
            self.poller.unregister(self.socket)
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.close()
            
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://127.0.0.1:{self.port}")
        self.poller.register(self.socket, zmq.POLLIN)
        
    def get_anomaly_context(self, frame_id=0, context="synthetic", incident_type="none"):
        """
        Polls the inference server for the current anomaly score.
        
        Returns:
            anomaly_score (float): 0.0 to 1.0
            anomaly_flag (int): 0 or 1
            incident_type (str): The incident type evaluated (for logging)
        """
        payload = {
            "action": "get_score",
            "frame_id": frame_id,
            "context": context,
            "incident_type": incident_type
        }
        
        try:
            self.socket.send_json(payload)
        except Exception as e:
            logging.error(f"VisionBridge send error: {e}")
            self._connect()
            return 0.0, 0, incident_type
            
        # Wait for reply with explicit timeout
        socks = dict(self.poller.poll(self.timeout_ms))
        if socks.get(self.socket) == zmq.POLLIN:
            try:
                reply = self.socket.recv_json()
                if reply.get("status") == "success":
                    return reply.get("anomaly_score", 0.0), reply.get("anomaly_flag", 0), reply.get("incident_type", "none")
            except Exception as e:
                logging.error(f"VisionBridge recv error: {e}")
        else:
            # Timeout hit! Avoid blocking the RL training loop.
            logging.debug("VisionBridge timeout, returning safe surrogate values.")
        
        # If we reach here, a timeout or error occurred. Reset the connection.
        self._connect()
        return 0.0, 0, incident_type
        
    def reset(self):
        """Clear any buffered state or stuck queues on environment reset."""
        self._connect()

if __name__ == "__main__":
    # Simple self-test
    logging.basicConfig(level=logging.DEBUG)
    bridge = VisionBridge(timeout_ms=1000)
    print("Testing 'stopped_vehicle'...")
    score, flag, inc = bridge.get_anomaly_context(incident_type="stopped_vehicle")
    print(f"Result: {score}, {flag}, {inc}")
    
    print("\nTesting 'none'...")
    score, flag, inc = bridge.get_anomaly_context(incident_type="none")
    print(f"Result: {score}, {flag}, {inc}")
