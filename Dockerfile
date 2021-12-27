FROM debian:stable

RUN apt-get update

RUN apt-get install -y gtk-doc-tools cmake gcc g++ git autoconf make automake libtool meson ninja-build
