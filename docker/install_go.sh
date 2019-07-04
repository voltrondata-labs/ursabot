#!/usr/bin/env bash

# Exit on any error
set -e

# Follow Go naming convention
declare -A archs
archs=([amd64]=amd64
       [ppc64le]=ppc64le
       [i386]=386)

# Validate arguments
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <architecture> <go-version>"
  exit
elif [[ -z ${archs[$1]} ]]; then
  echo "Unexpected architecture argument: ${1}"
  exit
fi

ARCH=${archs[$1]}
GOVERSION=$2

echo "Downloading Go SDK..."
wget -nv https://golang.org/dl/go${GOVERSION}.linux-${ARCH}.tar.gz -O /tmp/go-sdk.tar.gz
tar -C /usr/local -zxf /tmp/go-sdk.tar.gz
rm /tmp/go-sdk.tar.gz


