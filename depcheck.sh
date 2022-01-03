#!/usr/bin/env bash
DEPS=
libs=$(find ./install/lib -iname "*.so*")
for l in $libs; do
	deps=$(readelf -d $l | grep "NEEDED" | grep -Eo "[^\[]+.so(.[0-9]+)+")
	for d in $deps; do
		if [ -f "install/lib/$d" ]; then
			continue
		fi
		if [[ ! "$DEPS" =~ "$d" ]]; then
			DEPS="$DEPS $d"
		fi
	done
done
echo $DEPS
