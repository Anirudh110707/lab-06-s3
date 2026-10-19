
#!/usr/bin/env python3
"""Download Gutenberg books and upload them to a public S3 bucket."""

import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Read the three required command-line arguments."""
    if len(sys.argv) != 4:
        log.error("Usage: stage_books.py BOOK_LIST INDEX_HTML BUCKET")
        sys.exit(1)

    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir):
    """Download books and return the local file paths."""
    os.makedirs(dest_dir, exist_ok=True)
    paths = []

    try:
        urls = Path(list_file).read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError as error:
        log.error("Cannot read book list: %s", error)
        return paths

    for url in urls:
        url = url.strip()
        if not url:
            continue

        filename = Path(urlparse(url).path).name
        path = os.path.join(dest_dir, filename)

        if os.path.exists(path):
            log.info("Already downloaded: %s", filename)
            paths.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            Path(path).write_bytes(response.content)
            paths.append(path)
            log.info("Downloaded %s", filename)
            time.sleep(1)
        except (requests.RequestException, OSError) as error:
            log.error("Download failed for %s: %s", url, error)

    return paths


def create_bucket(bucket):
    """Create the S3 bucket if it does not exist."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info("Bucket already exists: %s", bucket)
        return True
    except ClientError as error:
        status = error.response.get(
            "ResponseMetadata", {}
        ).get("HTTPStatusCode")

        if status != 404:
            log.error("Cannot access bucket: %s", error)
            return False

    try:
        s3.create_bucket(Bucket=bucket)
        log.info("Created bucket: %s", bucket)
        return True
    except (ClientError, BotoCoreError) as error:
        log.error("Bucket creation failed: %s", error)
        return False


def make_public(bucket):
    """Configure public access to objects in the bucket."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{bucket}/*"
        }]
    }

    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False
            }
        )

        s3.put_bucket_policy(
            Bucket=bucket,
            Policy=json.dumps(policy)
        )

        log.info("Public access configured")
        return True
    except (ClientError, BotoCoreError) as error:
        log.error("Public access configuration failed: %s", error)
        return False


def upload_files(bucket, file_paths):
    """Upload downloaded books to S3."""
    count = 0

    for path in file_paths:
        try:
            s3.upload_file(
                path,
                bucket,
                os.path.basename(path),
                ExtraArgs={
                    "ContentType": "text/plain; charset=utf-8"
                }
            )
            count += 1
            log.info("Uploaded %s", os.path.basename(path))
        except (ClientError, BotoCoreError, OSError) as error:
            log.error("Upload failed for %s: %s", path, error)

    return count


def upload_index(bucket, index_path):
    """Upload the HTML index to S3."""
    try:
        s3.upload_file(
            index_path,
            bucket,
            "index.html",
            ExtraArgs={"ContentType": "text/html"}
        )
        log.info("Uploaded index.html")
        return True
    except (ClientError, BotoCoreError, OSError) as error:
        log.error("Index upload failed: %s", error)
        return False


def main():
    """Run the full download and upload workflow."""
    list_file, index_path, bucket = parse_args()

    paths = download_books(list_file, "books")

    if not paths:
        log.error("No books downloaded")
        sys.exit(1)

    if not create_bucket(bucket):
        sys.exit(1)

    if not make_public(bucket):
        sys.exit(1)

    count = upload_files(bucket, paths)
    index_ok = upload_index(bucket, index_path)

    if count != len(paths) or not index_ok:
        log.error("Not all uploads succeeded")
        sys.exit(1)

    log.info("Successfully uploaded %d books", count)
    log.info(
        "Public URL: https://%s.s3.amazonaws.com/index.html",
        bucket
    )


if __name__ == "__main__":
    main()



