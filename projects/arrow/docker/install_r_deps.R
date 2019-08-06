#!/usr/bin/env Rscript
#
# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

install.packages(
  c(
    'devtools',
    'curl',
    'xml2'
  ),
  repos = 'http://cran.rstudio.com'
)
devtools::install_github('romainfrancois/decor')

install.packages(
  c(
    'Rcpp',
    'dplyr',
    'stringr',
    'glue',
    'vctrs',
    'purrr',
    'assertthat',
    'fs',
    'tibble',
    'crayon',
    'testthat',
    'bit64',
    'hms',
    'lubridate',
    'covr',
    'lubridate',
    'pkgdown',
    'rmarkdown',
    'roxygen2'
  ),
  repos = 'https://cran.rstudio.com'
)
