#!/bin/sh
set -e

function error {
	echo "APK exited with non-zero code!" 
	echo "Make sure you're running this script in alpine!" 
	exit 1
}

# Add all of our required libraries 
apk add build-base clang libpng-static libpng-dev expat-static expat-dev zlib-dev zlib-static freetype-dev freetype-static fontconfig-static pixman-static || error
apk add libxcb-static libxrender-dev harfbuzz-static gtk-doc fontconfig-dev pixman-dev
apk add git autoconf make cmake automake libtool bzip2-static bzip2-dev brotli-dev brotli-static

# Build cairo
#-----------#
cd cairo #> /dev/null

export CC=clang 
export CXX=clang++
export PKG_CONFIG="pkg-config --static" 
export LDFLAGS=-static
export pixman_LIBS="/usr/lib/libpixman-1.a"
export png_LIBS="/usr/lib/libpng16.a"

./autogen.sh --enable-xlib=no --enable-xlib-xrender=no --enable-xlib-xcb=no --enable-xcb-shm=no --enable-ft --enable-egl=no --without-x --enable-glx=no --enable-wgl=no --enable-quartz=no --enable-svg=yes --enable-pdf=yes --enable-ps=yes --enable-gobject=no --enable-png --disable-static

make -j$(nproc) CFLAGS="-fPIC" LDFLAGS="-fPIC"

cd .. #> /dev/null
#-----------#
