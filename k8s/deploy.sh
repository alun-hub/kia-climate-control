#!/bin/bash
# Build the image, import it into k3s' containerd, and (re)deploy.
# Run from anywhere: k8s/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root

VERSION="v1-$(date +%s)"
IMAGE="localhost/kia-climate-control:${VERSION}"
TAR="/tmp/kia-climate-control-${VERSION}.tar"

echo "1/4  Bygger ${IMAGE} ..."
podman build --no-cache -t "${IMAGE}" -f k8s/Dockerfile .

echo "2/4  Importerar till k3s (namespace k8s.io) ..."
podman save "${IMAGE}" -o "${TAR}"
sudo k3s ctr -n k8s.io images import "${TAR}"
rm -f "${TAR}"

echo "3/4  Applicerar manifest ..."
kubectl apply -f k8s/manifests.yaml
kubectl -n kia set image deployment/kia-climate-control "app=${IMAGE}"

echo "4/4  Väntar på rollout ..."
kubectl -n kia rollout status deployment/kia-climate-control --timeout=180s

echo
echo "KLART: ${IMAGE}"
echo "  intern:  kubectl -n kia port-forward deploy/kia-climate-control 5000:5000"
echo "  publik:  https://kia.unixkonsult.se"
