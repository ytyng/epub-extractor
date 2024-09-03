#!/bin/bash

cd $(dirname $0)

for DIR in test-epubs/*; do
    if [ -d ${DIR} ]; then
        rm -r ${DIR}
    fi
done

for EPUB in test-epubs/*.epub; do
    echo ${EPUB}
    epub_extractor/epub_extract_jpeg.py ${EPUB}
done
