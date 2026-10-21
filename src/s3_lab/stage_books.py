#!/usr/bin/env python3

import logging
import os
import sys
import requests
import time
import boto3
import json
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")

def parse_args():
    """return (list_file, index_path, bucket) from the command line input."""
    if len(sys.argv) != 4:
        log.error("use: python stage_books.py <list_file> <index_path> <bucket>")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]

def download_books(list_file, dest_dir):
    """returns a list of the local paths of books to be passed into upload_files"""
    log.info(f'downloading books to {dest_dir}')
    os.makedirs(dest_dir, exist_ok=True)
    url_list = [line.strip() for line in open(list_file) if line.strip()]

    paths = []
    #loop through and download urls
    for url in url_list:
        filename = url.rstrip('/').split('/')[-1]
        path = os.path.join(dest_dir, filename)

        #check for path existence
        if os.path.exists(path):
            log.info(f'Already downloaded {path}, skipping')
            paths.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            open(path, "wb").write(response.content)
            log.info(f"Downloaded {url} to {path}")
            paths.append(path)
        except requests.RequestException as e:
            log.error(f'Error on {url}: {e}')

        time.sleep(1) # sleep/pause the function

    log.info("Download process completed.")
    return paths

def create_bucket(bucket):
	"""create the bucket to store data."""
	try:
		s3.head_bucket(Bucket=bucket)
		log.info(f"Bucket already exists")
		return True
		
	except ClientError as e:
		log.error(f"Error: {bucket} not found, creating bucket")
		try:
			s3.create_bucket(Bucket=bucket)
			log.info(f"Created bucket: {bucket}")
			return True
		except ClientError as e:
			log.error(f"Error creating bucket {bucket}: {e}")
			return False		
def make_public(bucket):
    """makes the bucket public on AWS"""

    # turn off the public access
    try:
        s3.put_public_access_block(
            Bucket = bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        log.info(f"Turned off Blocking Public Access for bucket {bucket}")
    except ClientError as e:
        log.error(f"Error turning off Block Public Access for bucket {bucket}: {e}")
        return False

    # create bucket policy
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*"
            }
        ]
    }

    # attach the bucket policy, within a try/except block
    try:
        s3.put_bucket_policy(Bucket=bucket, Policy = json.dumps(policy))
        log.info(f"Successfully attached public read policy to {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error attaching policy to {bucket}: {e}")
        return False

def upload_files(bucket, file_paths):
	"""Uploads files to bucket."""
	uploaded = 0
	for local_file in file_paths:
		key = os.path.basename(local_file)
		try:
			with open(local_file, "rb") as f:
				s3.put_object(
					Bucket=bucket,
					Key=key,
					Body=f,
					ContentType="text/plain; charset=utf-8"
				)
			uploaded += 1
			log.info(f"Uploaded {local_file} to s3://{bucket}/{key}")
		except FileNotFoundError:
			log.error(f"Local file not found: {local_file}")
		except ClientError as e:
			log.error(f"Error uploading object: {e}")
	return uploaded


def upload_index(bucket, index_path):
	"""Uploads index file to bucket."""
	try:
		s3.upload_file(
			Filename=index_path,
			Bucket=bucket,
			Key="index.html",
			ExtraArgs={"ContentType": "text/html"}
		)
		log.info(f"Index successfully uploaded.")
		return True
	except FileNotFoundError:
                log.error(f"Local file not found: {index_path}")
                return False
	except ClientError as e:
                log.error(f"Error uploading object: {e}")
                return False


def main():
    """Runs all of the functions in order, exiting if anything fails."""
    list_file, index_path, bucket = parse_args()
    
    book_list = download_books(list_file,"books")
    if not book_list:
        log.error("No books were downloaded, stopping")
        sys.exit(1)

    if not create_bucket(bucket):
        log.error(f"Could not create or access bucket {bucket}, stopping")
        sys.exit(1)

    if not make_public(bucket):
        log.error(f"Could not make bucket {bucket} public, stopping")
        sys.exit(1)

    uploaded = upload_files(bucket, book_list)
    index_ok = upload_index(bucket, index_path)

    url = f"https://{bucket}.s3.amazonaws.com/index.html"
    if uploaded == len(book_list) and index_ok:
        log.info(f"Success: uploaded {uploaded} of {len(book_list)} books and the index page to {bucket}")
        log.info(f"Public URL: {url}")
    else:
        log.error(f"Finished with errors: {uploaded} of {len(book_list)} books uploaded, index page uploaded: {index_ok}")
        log.info(f"Index page (may be incomplete): {url}")


if __name__ == "__main__":
    main()
