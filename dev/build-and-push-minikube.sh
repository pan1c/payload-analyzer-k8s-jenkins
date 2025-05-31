#!/bin/bash
# This script is a development artifact.
# Used for building and pushing the Docker image to a local registry on macOS/minikube.
# Not required for production CI/CD.
set -e

IMAGE_NAME=payload-analyzer
TAG=latest
REGISTRY=registry:57818

# Build the image for the local registry
docker build  -t $REGISTRY/$IMAGE_NAME:$TAG .

echo "Running docker push $REGISTRY/$IMAGE_NAME:$TAG"
# Push the image to the local registry
docker push $REGISTRY/$IMAGE_NAME:$TAG

echo "Image pushed to $REGISTRY/$IMAGE_NAME:$TAG for $PLATFORM"
