#!/usr/bin/env bash

# Runs this in a docker container for portability
ARGS="$@"
docker run --rm -u "$(id -u):$(id -g)" -v "$(pwd)":/build -w /build -e ARCH=amd64 strata-steamrt bash -c "./build.py $ARGS"
