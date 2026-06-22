#!/bin/bash
set -e

echo "Stopping NEXUS-ATMS Commercial Deployment..."

docker-compose down

echo "Services stopped successfully."
