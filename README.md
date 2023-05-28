## Strata Source dependencies for Linux

This repo contains the build scripts and patches necessary to build the libraries needed by Strata Source on Linux.

### Why?

Certain libraries we depend on (namely cairo and pango) bring in many shared libraries as dependencies, making it
difficult for Linux users to successfully run Strata-based games out of the box. These build scripts compile our
dependencies in such a way that they depend on only a few shared libraries, making them extremely portable.
