import json
import pytest

from aws_cdk import core
from applicationmetrics.applicationmetrics_stack import ApplicationmetricsStack


def get_template():
    app = core.App()
    ApplicationmetricsStack(app, "applicationmetrics")
    return json.dumps(app.synth().get_stack("applicationmetrics").template)


def test_sqs_queue_created():
    assert("AWS::SQS::Queue" in get_template())


def test_sns_topic_created():
    assert("AWS::SNS::Topic" in get_template())
