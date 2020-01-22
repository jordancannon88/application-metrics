import boto3
import os
import datetime
import logging
import json
from boto3.dynamodb.conditions import Key

# Get the service resource.
dynamodb = boto3.resource('dynamodb')

# Instantiate a table resource object without actually
# creating a DynamoDB table. Note that the attributes of this table
# are lazy-loaded: a request is not made nor are the attribute
# values populated until the attributes
# on the table resource are accessed or its load() method is called.
table = dynamodb.Table(os.environ['TABLE_NAME'])

# Set logger level.
logging.getLogger().setLevel(logging.INFO)


def handler(event, context):
    # Print event to logs.
    logging.info('request: {}'.format(json.dumps(event)))

    # Formatted dates to Common Log Format (dd/MMM/yyyy:HH:mm:ss +-hhmm)
    # https://httpd.apache.org/docs/1.3/logs.html#common
    try:
        start_date = datetime.datetime.strptime(event['start_date'], '%Y-%m-%d').strftime(
            "%d/%b/%Y:%H:%M:%S") + " +0000"
        end_date = datetime.datetime.strptime(event['end_date'], '%Y-%m-%d').replace(hour=23, minute=59, second=59,
                                                                                     microsecond=999999).strftime(
            "%d/%b/%Y:%H:%M:%S") + " +0000"

        logging.info('dates: {}'.format(json.dumps({'start': start_date, 'end': end_date})))
    except Exception as e:
        # Format error message as json.
        error_json = json.dumps({
            'type': 'ValidationException',
            'message': 'Your values are incorrect.'
        })
        logging.warning(error_json)
        raise Exception(error_json)

    # Check the start day is before the end date.
    if start_date > end_date:
        # Format error message as json.
        error_json = json.dumps({
            'type': 'ValidationException',
            'message': 'The start date is further in the future than the end date.'
        })
        logging.warning(error_json)
        raise Exception(error_json)

    # Grab data from DynamoDB.
    try:
        # Query for application name and date range.
        data = table.query(
            KeyConditionExpression=Key('application').eq(event['application']) & Key('created_at').between(start_date,
                                                                                                           end_date)
        )
    except Exception as e:
        # Format error message as json.
        error_json = json.dumps({
            'type': 'UnknownException',
            'message': 'Something went wrong with the database.'
        })
        logging.error(error_json)
        raise Exception(error_json)

    # TODO:: Fix json.dumps for decimals.

    logging.info('data: {}'.format(data))

    # The dict for holding our dates and counts.
    response = {}

    # Format and count dates.
    try:
        for items in data['Items']:
            # Format the created_at date of each entry (YYYY-mm-dd).
            created_at = datetime.datetime.strptime(items['created_at'][:-6], '%d/%b/%Y:%H:%M:%S').strftime("%Y-%m-%d")
            # Does the created_at date key already exists in the dict?
            if created_at in response:
                # It does, increment the value by 1.
                response[created_at] += 1
            else:
                # It does not, set a new key with a value of 1.
                response[created_at] = 1
    except Exception as e:
        # Format error message as json.
        error_json = json.dumps({
            'type': 'UnknownException',
            'message': 'Something went wrong with tallying dates.'
        })
        logging.error(error_json)
        raise Exception(error_json)

    logging.info('response: {}'.format(json.dumps(response)))

    return {
        'response': json.dumps(response)
    }
