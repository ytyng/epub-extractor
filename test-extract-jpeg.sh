#!/bin/bash

cd `dirname $0`

DIRS="test-epubs/*"
for DIR in ${DIRS}; do
    if [ -d ${DIR} ]; then
        rm -r ${DIR}
    fi
done

EPUBS="test-epubs/*.epub"
for EPUB in ${EPUBS}; do
    echo ${EPUB}
    epub_extractor/epub_extract_jpeg.py ${EPUB}
done
