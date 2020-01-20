import json
import logging

# Set logger level.
logging.getLogger().setLevel(logging.INFO)


def handler(event, context):
    # Print event to logs.
    logging.info('request: {}'.format(json.dumps(event)))

    return {
        'response': json.dumps({
            'message': 'Success!'
        })
    }
