#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import os

"""
EPUB ファイルの TOC を表示
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
    toc_table = epub_extractor.get_toc_table()
    epub_extractor.close()
    return toc_table


def main():
    parser = argparse.ArgumentParser(description='Dump EPUB toc data.')
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
    # epub_file = os.path.join(
    #     project_dir, 'test-epubs', 'BT000027007500100101900206_001.epub')
    epub_file = os.path.join(
        project_dir, 'test-epubs', 'BT000012354200100101900206_001.epub')
    data = procedure(epub_file)
    EpubExtractor.print_json(data)


if __name__ == '__main__':
    main()
    # test()
