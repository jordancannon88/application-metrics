import json
import pytest

from aws_cdk import core
from applicationmetrics.applicationmetrics_stack import ApplicationmetricsStack


def get_template():
    app = core.App()
    ApplicationmetricsStack(app, "applicationmetrics")
    return json.dumps(app.synth().get_stack("applicationmetrics").template)


def test_dynamo_db_table_created():
    assert ("AWS::DynamoDB::Table" in get_template())


def test_lambda_function_created():
    assert ("AWS::Lambda::Function" in get_template())


def test_lambda_function_environment_for_dynamo_db_table_created():
    assert ("TABLE_NAME" in get_template())
