#!/usr/bin/env bash

if [[ -z $EUID || $EUID -ne 0 ]]; then
	echo "Please run this script as root!"
	exit 1
fi

apt-get install -y gtk-doc-tools cmake gcc g++ git autoconf make automake libtool

