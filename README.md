## Chaos engine dependencies for Linux

This repo contains build scripts to compile all chaos engine dependencies for Linux.
Probably not useful for most, but if you want to reduce shared library dependencies for your project,
feel free to use this as a base. 

### Why?? 

Certain dependencies for our engine (cairo and pango specifically) bring in a lot of shared dependencies 
that make it difficult for Linux users to successfully run the game out of the box. This repo provides 
scripts to compile pango, cairo & others such that they only depend on a few libraries. 

### How to build

You can grab a release tarball from the releases section, build locally or build locally in a docker container.
The packages you need to install are listed in the Dockerfile. 

### How to update

Simply update the ref of the submodule you wish to update, push and wait for a release tarball to be published.
