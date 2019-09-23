#!/usr/bin/env bash

# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

# Exit on any error
set -e

# Follow docker naming convention
declare -A archs
archs=([amd64]=amd64)

# Validate arguments
if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <minio-version> <architecture> <installation-prefix>"
  exit 1
elif [[ -z ${archs[$2]} ]]; then
  echo "Unexpected architecture argument: ${2}"
  exit 1
elif [[ $1 != "latest" ]]; then
  echo "Cannot fetch specific versions of minio, only latest is supported."
  exit 1
fi

VERSION=$1
ARCH=${archs[$2]}
PREFIX=$3

wget -P ${PREFIX}/bin https://dl.min.io/server/minio/release/linux-${ARCH}/minio
chmod +x ${PREFIX}/bin/minio