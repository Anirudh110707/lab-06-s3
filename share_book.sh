
#!/bin/bash
set -euo pipefail

# Check that all required arguments were provided.
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET EXPIRATION" >&2
    exit 1
fi

BOOK_URL="$1"
BUCKET="$2"
EXPIRATION="$3"

# Validate the expiration value.
if ! [[ "$EXPIRATION" =~ ^[0-9]+$ ]] || \
   [ "$EXPIRATION" -lt 1 ] || \
   [ "$EXPIRATION" -gt 604800 ]; then
    echo "Expiration must be between 1 and 604800 seconds." >&2
    exit 1
fi

# Create the folder and download the book.
mkdir -p books
FILENAME="${BOOK_URL##*/}"
FILEPATH="books/$FILENAME"

echo "Downloading $FILENAME..."
curl --fail --location --silent --show-error \
    "$BOOK_URL" --output "$FILEPATH"

# Create the bucket if it does not already exist.
if ! aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Creating private bucket $BUCKET..."
    aws s3 mb "s3://$BUCKET" --region us-east-1
fi

# Upload the book with its content type.
echo "Uploading $FILENAME..."
aws s3 cp "$FILEPATH" "s3://$BUCKET/$FILENAME" \
    --content-type "text/plain; charset=utf-8"

# Generate and print the presigned URL.
echo "Presigned URL:"
aws s3 presign "s3://$BUCKET/$FILENAME" \
    --expires-in "$EXPIRATION" \
    --region us-east-1

