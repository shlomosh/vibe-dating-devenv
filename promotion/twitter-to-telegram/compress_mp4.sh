#!/bin/bash

if [ "$2" == "" ]; then
    echo "usage $0 <input-mp4-file> <output-mp4-file>"
    exit 1
fi

ffmpeg -i $1 -vcodec libx264 -crf 28 -preset slow -acodec aac $2

exit $?

