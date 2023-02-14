#!/usr/bin/env python3
"""
EPUB ファイルを jpeg に展開する
"""

import argparse

try:
    from .epub_extractor import EpubExtractor
except (ValueError, SystemError, ImportError):
    try:
        from epub_extractor import EpubExtractor
    except (ValueError, SystemError, ImportError):
        from epub_extractor.epub_extractor import EpubExtractor


def procedure(file_path, convert_png=True, delete_exists_dir=False):
    epub_extractor = EpubExtractor(file_path)
    epub_extractor.extract_images(
        convert_png=convert_png,
        delete_exists_dir=delete_exists_dir)
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
    parser.add_argument(
        '--delete-exists-dir', dest='delete_exists_dir', action='store_true',
        default=False,
        help='No png convert to jpeg')

    args = parser.parse_args()

    for epub_file in args.epub_files:
        procedure(epub_file, convert_png=not args.no_png_convert,
                  delete_exists_dir=args.delete_exists_dir)


if __name__ == '__main__':
    main()
