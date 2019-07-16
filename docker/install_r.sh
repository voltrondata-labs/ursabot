#!/usr/bin/env bash

# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

# Exit on any error
set -e

export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y software-properties-common apt-transport-https lsb-release
apt-key adv --keyserver keyserver.ubuntu.com \
            --recv-keys E298A3A825C0D65DFD57CBB651716619E084DAB9
add-apt-repository "deb https://cloud.r-project.org/bin/linux/ubuntu $(lsb_release -sc)-cran35/"
apt-get update -y
apt-get install -y r-base
