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
archs=([amd64]=x86_64
       [arm32v7]=armv7l
       [ppc64le]=ppc64le
       [i386]=x86)

# Validate arguments
if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <miniconda-version> <architecture> <installation-prefix>"
  exit 1
elif [[ -z ${archs[$2]} ]]; then
  echo "Unexpected architecture argument: ${2}"
  exit 1
fi

VERSION=$1
ARCH=${archs[$2]}
CONDA_PREFIX=$3

echo "Downloading Miniconda installer..."
wget -nv https://repo.continuum.io/miniconda/Miniconda3-${VERSION}-Linux-${ARCH}.sh -O /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p ${CONDA_PREFIX}
rm /tmp/miniconda.sh

ln -s ${CONDA_PREFIX}/etc/profile.d/conda.sh /etc/profile.d/conda.sh
echo "conda activate base" >> ~/.profile

# Configure conda
source /etc/profile.d/conda.sh
conda config --set show_channel_urls True

# Help with SSL timeouts to S3
conda config --set remote_connect_timeout_secs 12

# Setup conda-forge
conda config --add channels conda-forge
conda config --set channel_priority strict

# Update packages
conda update --all -y

# Clean up
conda clean --all -y
