#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

"""
EPUB ファイルを jpeg に展開する
"""

import argparse

try:
    from .epub_extractor import EpubExtractor
except (ValueError, SystemError):
    from epub_extractor import EpubExtractor
except ImportError:
    from epub_extractor.epub_extractor import EpubExtractor


def procedure(file_path, convert_png=True):
    epub_extractor = EpubExtractor(file_path)
    epub_extractor.extract_images(convert_png=convert_png)
    epub_extractor.close()


def main():
    parser = argparse.ArgumentParser(description='Extract Jpeg files in EPUB')
    parser.add_argument(
        'epub_files', metavar='EPUB-Files', type=str, nargs='+',
        help='Target Epub Files')
    parser.add_argument(
        '--no-png-convert', dest='no_png_convert', action='store_true',
        default=False,
        help='No png convert to jpeg')

    args = parser.parse_args()

    for epub_file in args.epub_files:
        procedure(epub_file, convert_png=not args.no_png_convert)


if __name__ == '__main__':
    main()
