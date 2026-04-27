import json

def lambda_handler(event, context):
    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
import boto3
import json
import logging
import requests
from requests_aws4auth import AWS4Auth

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
LEX_BOT_ID = 'BT6WQC8YTO'
LEX_BOT_ALIAS_ID = 'OKRMBNUNAA'
LEX_LOCALE = 'en_US'

lex = boto3.client('lexv2-runtime', region_name='us-east-1')

def get_keywords_from_lex(query):
    try:
        response = lex.recognize_text(
            botId=LEX_BOT_ID,
            botAliasId=LEX_BOT_ALIAS_ID,
            localeId=LEX_LOCALE,
            sessionId='search-session-' + ''.join(filter(str.isalnum, query))[:10],
            text=query
        )
        logger.info(f"Lex response: {json.dumps(response, default=str)}")
        slots = response.get('sessionState', {}).get('intent', {}).get('slots', {})
        keywords = []
        for slot_name, slot_val in slots.items():
            if slot_val and slot_val.get('value'):
                keywords.append(slot_val['value']['interpretedValue'].lower())
        return keywords
    except Exception as e:
        logger.error(f"Lex error: {str(e)}")
        return []

def search_photos(keywords):
    should_clauses = [{'match': {'labels': kw}} for kw in keywords]
    query = {
        'query': {
            'bool': {
                'should': should_clauses,
                'minimum_should_match': 1
            }
        }
    }
    url = f'{OPENSEARCH_ENDPOINT}/photos/_search'
    headers = {'Content-Type': 'application/json'}
    r = requests.get(url, auth=awsauth, json=query, headers=headers)
    logger.info(f"OpenSearch response: {r.status_code} - {r.text}")
    hits = r.json().get('hits', {}).get('hits', [])
    results = []
    for hit in hits:
        src = hit['_source']
        results.append({
            'url': f"https://{src['bucket']}.s3.amazonaws.com/{src['objectKey']}",
            'labels': src['labels']
        })
    return results

def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")
    query = event.get('queryStringParameters', {}).get('q', '')

    if not query:
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'results': []})
        }

    keywords = get_keywords_from_lex(query)
    logger.info(f"Keywords: {keywords}")

    if not keywords:
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'results': []})
        }

    results = search_photos(keywords)
    return {
        'statusCode': 200,
        'headers': {'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'results': results})
    }
