#!/usr/bin/env bash

# Exit on any error
set -e

# Follow docker naming convention
declare -A archs
archs=([amd64]=x86_64
       [arm32v7]=armv7l
       [ppc64le]=ppc64le
       [i386]=x86)

# Validate arguments
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <architecture> <installation-prefix>"
  exit
elif [[ -z ${archs[$1]} ]]; then
  echo "Unexpected architecture argument: ${1}"
  exit
fi

ARCH=${archs[$1]}
CONDA_PREFIX=$2

echo "Downloading Miniconda installer..."
wget -nv https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-${ARCH}.sh -O /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p ${CONDA_PREFIX}
rm /tmp/miniconda.sh

ln -s ${CONDA_PREFIX}/etc/profile.d/conda.sh /etc/profile.d/conda.sh
echo "conda activate base" >> /etc/profile

# Configure conda
source /etc/profile.d/conda.sh
conda config --set show_channel_urls True

# Help with SSL timeouts to S3
conda config --set remote_connect_timeout_secs 12

# Setup conda-forge
conda config --add channels conda-forge

# Update packages
conda update --all -y

# Clean up
conda clean --all -y
