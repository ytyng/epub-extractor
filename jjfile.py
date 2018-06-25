# -*- coding: utf-8 -*-

from __future__ import unicode_literals

menu = [
    ('cancel',
     ""),
    ('test',
     ["./test-dump-meta.sh; ./test-dump-toc.sh; ./test-extract-jpeg.sh"]),
    ('flake8',
     "flake8 ."),
    ('upload pypi',
     "./setup.py sdist; twine upload --skip-existing dist/*"),
]
