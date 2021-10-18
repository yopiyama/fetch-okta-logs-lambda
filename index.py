import os
import dateutil.parser
from datetime import datetime, timedelta
import requests
import json
import time
import logging
import hashlib
import gzip
from botocore.exceptions import ClientError
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SEND_BUCKET_NAME = os.environ.get('SEND_BUCKET_NAME', '')
BUCKET_PREFIX = os.environ.get('BUCKET_PREFIX', '')

ssmclient = boto3.client('ssm')

api_token = os.environ.get(
    'API_TOKEN', '')
api_uri = os.environ.get('ORG_URL', '')

def get_parameter(parameter_name, default):
    try:
        return(ssmclient.get_parameter(Name=parameter_name)["Parameter"]['Value'])
    except ClientError as e:
        if e.response['Error']['Code'] == 'ParameterNotFound':
            return default


def put_parameter(parameter_name, value):
    ssmclient.put_parameter(Name=parameter_name,
                            Type='String', Value=value, Overwrite=True)


def send_to_s3(records, since):
    log_jsonl = ''
    last_published = datetime.strptime(since, '%Y-%m-%dT%H:%M:%S.%fZ')

    for record in records:
        log_jsonl += json.dumps(record, ensure_ascii=False) + '\n'
        # Get the last published time
        last_jsonl = json.loads(json.dumps(record, ensure_ascii=False))
        if datetime.strptime(last_jsonl['published'], '%Y-%m-%dT%H:%M:%S.%fZ') > last_published:
            last_published = datetime.strptime(last_jsonl['published'], '%Y-%m-%dT%H:%M:%S.%fZ')

    prefix_date = last_published.strftime('%Y/%m/%d/%H/')
    prefix = BUCKET_PREFIX + prefix_date
    last_date = last_published.strftime('%Y-%m-%d-%H-%M-%S')
    md5_value = hashlib.md5(log_jsonl.encode('UTF-8')).hexdigest()
    filename = 'okta-logs-' + \
        last_date + '-' + md5_value + '.jsonl.gz'

    with gzip.open('/tmp/' + filename, mode='wt') as fp:
        fp.write(log_jsonl)

    s3 = boto3.resource('s3')
    obj = s3.Object(SEND_BUCKET_NAME, prefix + filename)
    obj.upload_file('/tmp/' + filename)

    delta_last_published = last_published + timedelta(seconds=1)

    return delta_last_published.isoformat('T', timespec='milliseconds') + 'Z'


def getLogs(startTime):
    logs_url = 'https://' + api_uri + '/api/v1/logs'
    headers = {'Authorization': 'SSWS ' + api_token}
    params = {'since': startTime, 'sortOrder': 'ASCENDING', 'limit': 1000}
    # params = {'since': startTime, 'sortOrder': 'ASCENDING', 'filter':'actor.alternateId eq "username" and outcome.result eq "FAILURE"', 'limit': 1000}
    logger.info("params = {0}".format(params))

    try:
        logger.info('Sending requests {0}'.format(logs_url))
        events = requests.get(logs_url, headers=headers, params=params)
    except Exception as e:
        logger.info("Exception {0}".format(str(e)))
        return []
    if not events or events.status_code != 200:
        logger.info("Received unexpected " + str(events) + " response from Okta Server {0}.".format(
                        logs_url))
        return []

    ret_list = []

    for e in events.json():
        if e == 'errorCode':
            break
        ret_list.append(e)
    old_link = ""

    while events.links['next']['url'] != old_link and 'next' in events.links:
        old_link = events.links['next']['url']
        try:
            logger.info('Sending requests {0}'.format(
                events.links['next']['url']))
            events = requests.get(
                events.links['next']['url'], headers=headers)
        except Exception as e:
            logger.info("Exception {0}".format(str(e)))
            return []
        if not events or events.status_code != 200:
            logger.info("Received unexpected " + str(events) + " response from Okta Server {0}.".format(
                            events.status_code))
            return []
        for e in events.json():
            if e == 'errorCode':
                break
            ret_list.append(e)
    return ret_list

def get_latest_logs():

    param = '/okta-logs/lastquerytime'
    new_date = datetime.now() - timedelta(minutes=60)
    since = get_parameter(
        param, str(new_date.isoformat('T', timespec='milliseconds') + 'Z'))

    logger.info('Getting Okta Logs')
    records = getLogs(since)

    if records:
        # print(json.dumps(records))
        last_published = send_to_s3(records, since)

        logger.info('Received records {0}'.format(str(len(records))))
        put_parameter(param, last_published)
    else:
        logger.info('No Received records')

def lambda_handler(event, context):
    get_latest_logs()

if __name__ == "__main__":
    get_latest_logs()
