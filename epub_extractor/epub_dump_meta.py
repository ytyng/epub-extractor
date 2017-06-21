#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import os

"""
EPUB ファイルの Meta を表示
"""

import argparse

try:
    from .epub_extractor import EpubExtractor
except (ValueError, SystemError):
    from epub_extractor import EpubExtractor
except ImportError:
    from epub_extractor.epub_extractor import EpubExtractor


def procedure(file_path):
    epub_extractor = EpubExtractor(file_path)
    meta = epub_extractor.meta
    metadata = meta.as_ordered_dict()
    epub_extractor.close()
    return metadata


def main():
    parser = argparse.ArgumentParser(description='Dump EPUB Meta information.')
    parser.add_argument(
        'epub_files', metavar='EPUB-Files', type=str, nargs='+',
        help='Target Epub Files')

    args = parser.parse_args()

    if len(args.epub_files) > 1:
        out = []
        for epub_file in args.epub_files:
            out.append(procedure(epub_file))
    else:
        out = procedure(args.epub_files[0])

    EpubExtractor.print_json(out)


def test():
    project_dir = os.path.dirname(os.path.dirname(__file__))
    epub_file = os.path.join(
        project_dir, 'test-epubs', 'BT000027007500100101900206_001.epub')
    data = procedure(epub_file)
    EpubExtractor.print_json(data)


if __name__ == '__main__':
    main()
    # test()
