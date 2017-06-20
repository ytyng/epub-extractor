#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import os

"""
EPUB ファイルの Meta を表示
"""

import argparse
import six
import json

try:
    from .epub_extractor import EpubExtractor
except (ValueError, SystemError):
    from epub_extractor import EpubExtractor
except ImportError:
    from epub_extractor.epub_extractor import EpubExtractor


def procedure(file_path):
    epub_extractor = EpubExtractor(file_path)
    meta = epub_extractor.meta
    d = meta.as_ordered_dict()
    if six.PY2:
        print(json.dumps(d, ensure_ascii=False, indent=2).encode(
            'utf-8', errors='ignore'))

    else:
        print(json.dumps(d, ensure_ascii=False, indent=2))

    epub_extractor.close()


def main():
    parser = argparse.ArgumentParser(description='Dump EPUB Meta information.')
    parser.add_argument(
        'epub_files', metavar='EPUB-Files', type=str, nargs='+',
        help='Target Epub Files')

    args = parser.parse_args()

    for epub_file in args.epub_files:
        procedure(epub_file)


def test():
    project_dir = os.path.dirname(os.path.dirname(__file__))
    epub_file = os.path.join(
        project_dir, 'test-epubs', 'BT000029028900100101900209_001.epub')
    procedure(epub_file)


if __name__ == '__main__':
    main()
    # test()
