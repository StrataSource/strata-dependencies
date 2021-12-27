#!/bin/bash

# Runs this in a docker container for portability
docker run --rm -v "$(pwd)":"$(pwd)" -w "$(pwd)" -e ARCH=amd64 chaos-dep-builder "./build.sh"

