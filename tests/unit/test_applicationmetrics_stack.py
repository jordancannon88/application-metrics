import json
import pytest

from aws_cdk import core
from applicationmetrics.applicationmetrics_stack import ApplicationmetricsStack


def get_template():
    app = core.App()
    ApplicationmetricsStack(app, "applicationmetrics")
    return json.dumps(app.synth().get_stack("applicationmetrics").template)


# Code
