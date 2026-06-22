#!/bin/bash
set -e

echo "Starting NEXUS-ATMS Commercial Deployment..."

# Build and start services
docker-compose up -d --build

echo "Services started:"
echo "- Stream-A (GPU) running on port 8000"
echo "- Hybrid Runtime (CPU) running on port 8001"
echo "- Digital Twin Frontend running on port 3000"

echo "To view logs, run: docker-compose logs -f"
