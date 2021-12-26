#!/usr/bin/env bash
set -e

function error {
	echo "APK exited with non-zero code!" 
	echo "Make sure you're running this script in alpine!" 
	exit 1
}

# Add all of our required libraries 
if [ ! -z $RUNNING_ALPINE ]; then
	apk add build-base clang libpng-static libpng-dev expat-static expat-dev zlib-dev zlib-static freetype-dev freetype-static fontconfig-static pixman-static || error
	apk add libxcb-static libxrender-dev harfbuzz-static gtk-doc fontconfig-dev pixman-dev
	apk add git autoconf make cmake automake libtool bzip2-static bzip2-dev brotli-dev brotli-static
fi

INCDIR="$PWD/install/include"
LIBDIR="$PWD/install/lib"

#------------------------#
# Build libz
#------------------------#
pushd zlib > /dev/null

export CFLAGS="-fPIC"
./configure --static --64 --prefix="$PWD/../install"
make install -j$(nproc)

popd > /dev/null
#------------------------#

#------------------------#
# Build bzip2
#------------------------#
pushd bzip2 > /dev/null

make install -j$(nproc) CFLAGS=-fPIC LDFLAGS=-fPIC PREFIX="$PWD/../install"

popd > /dev/null
#------------------------#

#------------------------#
# Build brotli
#------------------------#
pushd brotli > /dev/null

./bootstrap
export CFLAGS="-fPIC"
./configure --enable-static --disable-shared --prefix="$PWD/../install"
make install -j$(nproc)

popd > /dev/null
#------------------------#

#------------------------#
# Build libpng
#------------------------#
pushd libpng > /dev/null

export CFLAGS="-fPIC"
./configure --enable-static --disable-shared --prefix="$PWD/../install"
make install -j$(nproc)

# --disable-shared does nothing, cool! 
rm -f ../install/lib/libpng*.so*

popd > /dev/null
#------------------------#

#------------------------#
# Build jsonc
#------------------------#
pushd json-c > /dev/null

mkdir -p build && cd build
../cmake-configure --enable-static --prefix="$PWD/../../install" -- -DDISABLE_EXTRA_LIBS=ON -DCMAKE_BUILD_TYPE="Release"
make install -j$(nproc)

# Once again, no way to cull shared objects!
rm -f "$PWD"/../../install/lib/libjson-c*.so*

popd > /dev/null
#------------------------#


# Uncomment me when libxml2 is required, if ever!
#------------------------#
# Build libxml2
#------------------------#
#pushd libxml2 > /dev/null
#
#export CFLAGS="-fPIC"
#
# Make sure we do not pull anything in, fontconfig needs to do that!
#export Z_LIBS=""
#export LZMA_LIBS=""
#export ICU_LIBS=""
#
# Why does libxml2 have python bindings??
#./autogen.sh --prefix="$PWD/../install" --enable-static --without-icu --enable-shared=no --without-python
#make install -j$(nproc)
#
#popd > /dev/null
#------------------------#

#------------------------#
# Build expat
#------------------------#
pushd libexpat/expat > /dev/null

./buildconf.sh
export CFLAGS="-fPIC"

./configure --enable-static --enable-shared=no --prefix="$PWD/../../install"
make install -j$(nproc)

popd > /dev/null
#------------------------#

#------------------------#
# Build fontconfig
#------------------------#
pushd fontconfig > /dev/null

# Override pkgconfig stuff
export CFLAGS="-fPIC -I$INCDIR"
export FREETYPE_CFLAGS="-I$INCDIR/freetype2 -I$INCDIR/freetype2/freetype"
export FREETYPE_LIBS="-L$LIBDIR -lfreetype"
export EXPAT_CFLAGS=""
export EXPAT_LIBS="$LIBDIR/libexpat.a"
export JSONC_CFLAGS="-I$INCDIR/json-c"
export JSONC_LIBS="$LIBDIR/libjson-c.a"

./autogen.sh --enable-static=no --prefix="$PWD/../install" --with-expat="$PWD/../install" 
make install -j$(nproc)

popd > /dev/null
#------------------------#

#------------------------#
# Build freetype
#------------------------#
pushd freetype > /dev/null

# Setup pkgconfig overrides
export LDFLAGS="-L$(realpath ../install/lib) -Wl,--no-undefined"
export ZLIB_LIBS=""
export BZIP2_LIBS=""
# Manually specify link order for png, bz2, zlib and libm to avoid unresolved symbols due to single pass linking
export LIBPNG_LIBS="$(realpath ../install/lib/libpng.a) -lbz2 -lz -lm"
export BROTLI_LIBS="$(realpath ../install/lib/libbrotlidec.a) $(realpath ../install/lib/libbrotlienc.a) $(realpath ../install/lib/libbrotlicommon.a)"
export CFLAGS="-fPIC"

./autogen.sh
./configure --with-harfbuzz=no --enable-shared --disable-static --prefix="$PWD/../install"
make install -j$(nproc)

popd > /dev/null
#------------------------#

exit 1

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
