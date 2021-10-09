#!/bin/bash

# Runs this in an alpine container
docker run --rm -v "$(pwd)":"$(pwd)" -w "$(pwd)" -e ARCH=amd64 alpine "./build.sh"

