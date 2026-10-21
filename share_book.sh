#!/bin/bash
set -euo pipefail

#Check that all arguments are provided
if [ "$#" -lt 3 ]; then
	echo "Usage: $0 <URL> <BUCKET> <EXPIRE>"
	exit 1
fi

# Defines positional arguments
URL=$1
BUCKET=$2
EXPIRE=$3

# Download the book with curl into books/, keeping the filename from the URL
FILE="$(basename "$URL")"
mkdir -p books  # Create books/ if it doesn't exist (no error if it already does)
curl -fsSL -o "books/$FILE" "$URL"
echo "Downloaded $URL to books/$FILE"

# Create the bucket if it doesn't already exist
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket $BUCKET already exists"
else
    aws s3 mb "s3://$BUCKET"
fi

# Upload the book as plain text so browsers display it instead of downloading it (object stays private)
aws s3 cp "books/$FILE" "s3://$BUCKET/$FILE" --content-type "text/plain; charset=utf-8"

# Generate a temporary presigned URL for the book that expires after $EXPIRES seconds, and print it
aws s3 presign "s3://$BUCKET/$FILE" --expires-in "$EXPIRE"
