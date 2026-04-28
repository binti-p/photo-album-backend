# version 1.0

import boto3
import json
import logging
import datetime
import requests
from requests_aws4auth import AWS4Auth
from urllib.parse import unquote_plus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

region = 'us-east-1'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    region,
    'es',
    session_token=credentials.token
)

OPENSEARCH_ENDPOINT = 'https://search-photos-6g6nytncqngju6alnkyxxi2trq.aos.us-east-1.on.aws'
INDEX = 'photos'

rekognition = boto3.client('rekognition', region_name=region)
s3 = boto3.client('s3', region_name=region)

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        logger.info(f"Processing {key} from {bucket}")

        try:
            rek_response = rekognition.detect_labels(
                Image={'S3Object': {'Bucket': bucket, 'Name': key}},
                MaxLabels=10,
                MinConfidence=70
            )
            labels = [label['Name'].lower() for label in rek_response['Labels']]
            logger.info(f"Rekognition labels: {labels}")
        except Exception as e:
            logger.error(f"Rekognition error: {str(e)}")
            raise

        try:
            head = s3.head_object(Bucket=bucket, Key=key)
            metadata = head.get('Metadata', {})
            custom_labels_raw = metadata.get('customlabels', '')
            if custom_labels_raw:
                custom = [l.strip().lower() for l in custom_labels_raw.split(',')]
                labels.extend(custom)
                logger.info(f"Custom labels: {custom}")
        except Exception as e:
            logger.error(f"S3 metadata error: {str(e)}")
            raise

        timestamp = datetime.datetime.now().isoformat()
        doc = {
            'objectKey': key,
            'bucket': bucket,
            'createdTimestamp': timestamp,
            'labels': labels
        }

        try:
            url = f'{OPENSEARCH_ENDPOINT}/{INDEX}/_doc'
            headers = {'Content-Type': 'application/json'}
            r = requests.post(url, auth=awsauth, json=doc, headers=headers)
            logger.info(f"OpenSearch response: {r.status_code} - {r.text}")
        except Exception as e:
            logger.error(f"OpenSearch error: {str(e)}")
            raise

    return {'statusCode': 200, 'body': 'Done'}
