import { useState, useEffect } from 'react';

export interface NexusState {
  tick: number;
  junction_id: string;
  traffic: {
    queue: Record<string, number>;
    wait: Record<string, number>;
  };
  anomalies: Record<string, number>;
  signals: string;
  rl: {
    action: number | null;
    probabilities: number[];
  } | null;
}

export function useNexusStream() {
  const [state, setState] = useState<NexusState | null>(null);
  const [connected, setConnected] = useState(false);
  const [history, setHistory] = useState<NexusState[]>([]);

  useEffect(() => {
    let ws: WebSocket;
    let retryInterval: NodeJS.Timeout;

    const connect = () => {
      try {
        ws = new WebSocket('ws://localhost:8001/ws');

        ws.onopen = () => {
          console.log('Connected to NEXUS runtime');
          setConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'state_update') {
              setState(data);
              setHistory(prev => [...prev.slice(-100), data]);
            }
          } catch (e) {
            console.error('Failed to parse websocket message', e);
          }
        };

        ws.onclose = () => {
          console.log('Disconnected from NEXUS runtime. Retrying...');
          setConnected(false);
        };
        
        ws.onerror = (e) => {
          console.error("WebSocket error:", e);
          ws.close();
        }

      } catch (error) {
        console.error("Connection error:", error);
      }
    };

    connect();

    retryInterval = setInterval(() => {
      if (!connected && (!ws || ws.readyState === WebSocket.CLOSED)) {
        connect();
      }
    }, 3000);

    return () => {
      clearInterval(retryInterval);
      if (ws) ws.close();
    };
  }, [connected]);

  // Aggregate metrics
  const totalQueue = state ? Object.values(state.traffic.queue).reduce((a, b) => a + b, 0) : 0;
  const maxWait = state ? Math.max(...Object.values(state.traffic.wait), 0) : 0;
  const maxAnomaly = state && state.anomalies ? Math.max(...Object.values(state.anomalies), 0) : 0;

  return { state, history, connected, totalQueue, maxWait, maxAnomaly };
}
