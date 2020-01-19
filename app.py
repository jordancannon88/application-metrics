#!/usr/bin/env python3

from aws_cdk import core

from applicationmetrics.applicationmetrics_stack import ApplicationmetricsStack


app = core.App()
ApplicationmetricsStack(app, "applicationmetrics", env={'region': 'us-west-2'})

app.synth()
