# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

from datetime import datetime

from recommonmark.parser import CommonMarkParser

extensions = []
templates_path = ["templates", "_templates", ".templates"]
source_suffix = [".rst", ".md"]
source_parsers = {
    ".md": CommonMarkParser,
}
master_doc = "index"
project = "sagemaker-rightline"
copyright = str(datetime.now().year)
version = "stable"
release = "stable"
exclude_patterns = ["_build"]
pygments_style = "sphinx"
htmlhelp_basename = "sagemaker-rightline"
html_theme = "sphinx_rtd_theme"
file_insertion_enabled = False
latex_documents = [
    ("index", "sagemaker-rightline.tex", "sagemaker-rightline Documentation", "", "manual"),
]
