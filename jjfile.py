# -*- coding: utf-8 -*-

from __future__ import unicode_literals

menu = [
    ('cancel',
     ""),
    ('test',
     ["./test-dump-meta.sh; ./test-dump-toc.sh; ./test-extract-jpeg.sh"]),
    ('flake8',
     "flake8 ."),
    ('register pypi',
     "twine register dist/epub-extractor-0.1.4.tar.gz"),
    ('upload pypi',
     "twine upload dist/epub-extractor-0.1.4.tar.gz"),
    ('__register pypi',
     "./setup.py register"),
    ('__upload pypi',
     "./setup.py sdist upload"),
]
