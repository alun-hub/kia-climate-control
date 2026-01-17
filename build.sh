#!/bin/bash
# Build and deploy script for Kia Climate Control

set -e

echo "🚗 Kia EV6 Climate Control - Build & Deploy Script"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="kia-climate-control"
CONTAINER_NAME="kia-climate-control"
PORT=5000

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    print_error "Podman is not installed. Please install podman first."
    exit 1
fi

# Menu
echo "Välj åtgärd:"
echo "1. Bygg container image"
echo "2. Kör container"
echo "3. Stoppa container"
echo "4. Visa loggar"
echo "5. Fullständig deploy (bygg + kör)"
echo "6. Rensa allt och starta om"
echo ""
read -p "Ange val (1-6): " choice

case $choice in
    1)
        print_status "Bygger container image..."
        podman build -t ${IMAGE_NAME}:latest .
        print_success "Image byggd: ${IMAGE_NAME}:latest"
        ;;
    2)
        print_status "Kontrollerar om container redan körs..."
        if podman ps -a | grep -q ${CONTAINER_NAME}; then
            print_status "Tar bort befintlig container..."
            podman rm -f ${CONTAINER_NAME}
        fi

        print_status "Skapar data-mapp om den inte finns..."
        mkdir -p ./data

        print_status "Startar container..."
        podman run -d \
          --name ${CONTAINER_NAME} \
          -p ${PORT}:${PORT} \
          --env-file .env \
          -v ./data:/app/data:Z \
          --restart unless-stopped \
          ${IMAGE_NAME}:latest

        print_success "Container startad!"
        print_status "Webbgränssnitt: http://localhost:${PORT}"
        ;;
    3)
        print_status "Stoppar container..."
        podman stop ${CONTAINER_NAME}
        print_success "Container stoppad!"
        ;;
    4)
        print_status "Visar loggar (Ctrl+C för att avsluta)..."
        podman logs -f ${CONTAINER_NAME}
        ;;
    5)
        print_status "Fullständig deploy - Bygg + Kör..."

        # Build
        print_status "Steg 1/3: Bygger image..."
        podman build -t ${IMAGE_NAME}:latest .
        print_success "Image byggd!"

        # Stop and remove old container
        print_status "Steg 2/3: Rensar gammal container..."
        podman rm -f ${CONTAINER_NAME} 2>/dev/null || true

        # Create data directory
        mkdir -p ./data

        # Run
        print_status "Steg 3/3: Startar ny container..."
        podman run -d \
          --name ${CONTAINER_NAME} \
          -p ${PORT}:${PORT} \
          --env-file .env \
          -v ./data:/app/data:Z \
          --restart unless-stopped \
          ${IMAGE_NAME}:latest

        print_success "Deployment klar!"
        echo ""
        print_status "Webbgränssnitt: http://localhost:${PORT}"
        print_status "Health check: http://localhost:${PORT}/api/health"
        echo ""
        print_status "Vill du se loggarna? (y/n)"
        read -p "> " show_logs
        if [ "$show_logs" = "y" ]; then
            podman logs -f ${CONTAINER_NAME}
        fi
        ;;
    6)
        print_status "Rensar allt och startar om..."

        print_status "Stoppar och tar bort container..."
        podman rm -f ${CONTAINER_NAME} 2>/dev/null || true

        print_status "Tar bort image..."
        podman rmi -f ${IMAGE_NAME}:latest 2>/dev/null || true

        print_status "Bygger ny image..."
        podman build -t ${IMAGE_NAME}:latest .

        print_status "Skapar data-mapp..."
        mkdir -p ./data

        print_status "Startar container..."
        podman run -d \
          --name ${CONTAINER_NAME} \
          -p ${PORT}:${PORT} \
          --env-file .env \
          -v ./data:/app/data:Z \
          --restart unless-stopped \
          ${IMAGE_NAME}:latest

        print_success "Allt klart! Systemet är återställt och körs."
        print_status "Webbgränssnitt: http://localhost:${PORT}"
        ;;
    *)
        print_error "Ogiltigt val!"
        exit 1
        ;;
esac

echo ""
print_success "Klart! ✨"
