#!/bin/bash

# Runs this in a docker container for portability
docker run --rm -u "$(id -u):$(id -g)" -v "$(pwd)":/build -w /build -e ARCH=amd64 chaos-dep-builder bash -c "./build.sh $@"

