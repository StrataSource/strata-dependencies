FROM debian:stable

RUN apt-get update && apt-get install -y gtk-doc-tools cmake gcc g++ git autoconf make automake libtool meson ninja-build \
	texi2html texinfo \
	python3 python-setuptools python3-setuptools-git python3-pip bc \
	gperf gettext autopoint \
	wget curl \
	bison flex yasm nasm libvulkan-dev \
	glslang-tools \
	xorg-dev libwayland-dev \
	libasound2-dev libpulse-dev libaudio-dev \
	libjack-dev libx11-dev libxext-dev libxrandr-dev \
	libxcursor-dev libxfixes-dev libxi-dev \
	libxinerama-dev libxxf86vm-dev libxss-dev libgl1-mesa-dev \
	libdbus-1-dev libudev-dev libgles2-mesa-dev \
	libegl1-mesa-dev libibus-1.0-dev fcitx-libs-dev libsamplerate0-dev \
	libsndio-dev libwayland-dev libxkbcommon-dev libdrm-dev libgbm-dev
