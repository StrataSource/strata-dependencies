FROM debian:stable

RUN apt-get update

RUN apt-get install -y gtk-doc-tools cmake gcc g++ git autoconf make automake libtool meson ninja-build
RUN apt-get install -y texi2html texinfo
RUN apt-get install -y python3 python-setuptools python3-setuptools-git python3-pip
RUN apt-get install -y bc
RUN apt-get install -y gperf gettext autopoint
RUN apt-get install -y wget curl
RUN apt-get install -y bison flex yasm nasm libvulkan-dev
RUN apt-get install -y glslang-tools
