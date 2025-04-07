#!/usr/bin/env bash

rm -rf install

git submodule foreach git reset --hard
git submodule foreach git clean -ffdx
