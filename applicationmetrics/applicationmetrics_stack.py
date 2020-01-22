from aws_cdk import (
    core,
    aws_apigateway,
    aws_cloudwatch,
    aws_cloudwatch_actions,
    aws_dynamodb,
    aws_iam,
    aws_lambda,
    aws_logs,
    aws_sns,
    aws_sns_subscriptions,
)

import json

# Emails for receiving alerts.
notification_emails = [
    'XXX@gmail.com',
    'XXX@yahoo.com'
]


class ApplicationmetricsStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # TODO:: Remove all unnecessary comments when finished.
        # TODO:: Add tags for resources.
        # TODO:: Insert metadata of client "referrer" for request integration.
        # TODO:: Add CloudWatch logs to s3 to glacier policy

        # [ CREATE ] DynamoDB:
        #
        # - 100% integration with the AWS API allows other AWS resources to directly access the database. Less
        #   resources are involved meaning easier maintenance.
        #
        # - Encryption at rest.

        table = aws_dynamodb.Table(self, 'table',
                                   partition_key=aws_dynamodb.Attribute(
                                       name='application',
                                       type=aws_dynamodb.AttributeType.STRING
                                   ),
                                   sort_key=aws_dynamodb.Attribute(
                                       name='created_at',
                                       type=aws_dynamodb.AttributeType.STRING
                                   ),
                                   # On-demand pricing and scaling. You only pay for what you use and
                                   # there is no read and write capacity for the table or its global
                                   # secondary indexes.
                                   billing_mode=aws_dynamodb.BillingMode.PAY_PER_REQUEST
                                   )
        # [ CREATE ] Lambda:

        function_post = aws_lambda.Function(self, 'post',
                                            runtime=aws_lambda.Runtime.PYTHON_3_6,
                                            handler='function_post.handler',
                                            code=aws_lambda.Code.asset('./lambdas/applications'),
                                            tracing=aws_lambda.Tracing.ACTIVE
                                            )

        # [ CREATE ] DynamoDB: Permission:

        table.grant_read_data(function_post)

        # [ CREATE ] Lambda: Environment:

        function_post.add_environment('TABLE_NAME', table.table_name)

        # [ CREATE ] Log: LogGroup:
        #
        # - TODO:: FIX: https://github.com/aws/aws-cdk/issues/3838 (Soon to be fixed)

        # Creates new Lambda Log Group.

        # function_post_log_group = aws_logs.LogGroup(self, 'LogGroup',
        #                                             log_group_name='/aws/lambda/' + function_post.function_name
        #                                             )

        # Finds existing Lambda Log Group.

        function_post_log_group = aws_logs.LogGroup.from_log_group_name(self, 'LogGroup',
                                                                        log_group_name='/aws/lambda/' + function_post.function_name
                                                                        )

        # [ CREATE ] Log: MetricFilter:

        aws_logs.MetricFilter(self, 'LambdaLogErrorReport',
                              filter_pattern=aws_logs.FilterPattern.all_terms('[ERROR]'),
                              log_group=function_post_log_group,
                              metric_namespace='Lambdas',
                              metric_name='LambdaErrors',
                              default_value=0,
                              metric_value='1',
                              )

        aws_logs.MetricFilter(self, 'LambdaLogMemoryUsage',
                              filter_pattern=aws_logs.FilterPattern.literal(
                                  '[report="REPORT", request_id_name, request_id_value, duration_name, duration_value, duration_unit, duration_billed_name, duration_billed_name_2, duration_billed_value, duration_billed_unit, memory_max_name, memory_max_name_2, memory_max_value, memory_max_unit, memory_used_name, memory_used_name_2, memory_used_name_3, memory_used_value, memory_used_unit]'),
                              log_group=function_post_log_group,
                              metric_namespace='Lambdas',
                              metric_name='LambdaMemory',
                              default_value=0,
                              metric_value="$memory_used_value",
                              )

        # [ CREATE ] IAM: Role
        #
        # - Allows API Gateway to assume this Role with the policies that allow access to DynamoDB.

        role = aws_iam.Role(self, 'ApiGatewayServiceRole',
                            assumed_by=aws_iam.ServicePrincipal('apigateway.amazonaws.com')
                            )

        # [ ADD ] IAM: Role: Policy

        role.add_to_policy(aws_iam.PolicyStatement(
            resources=[
                table.table_arn
            ],
            actions=[
                'dynamodb:PutItem',
            ]
        ))

        # [ CREATE ] API Gateway:

        api = aws_apigateway.RestApi(self, 'api_application_metrics',
                                     default_cors_preflight_options=aws_apigateway.CorsOptions(
                                         allow_origins=['*'],
                                     ),
                                     deploy_options=aws_apigateway.StageOptions(
                                         logging_level=aws_apigateway.MethodLoggingLevel.INFO,
                                         # Log full requests/responses data
                                         data_trace_enabled=True,
                                         # Enable Detailed CloudWatch Metrics
                                         metrics_enabled=True,
                                         # Enable X-Ray Tracing
                                         tracing_enabled=True
                                     )
                                     )

        # [ ADD ] API Gateway: Resource

        api_resource_applications = api.root.add_resource('applications')

        # [ ADD ] API Gateway: Validator

        api_validator_request = api.add_request_validator('DefaultValidator',
                                                          validate_request_body=True
                                                          )

        # [ CREATE ] API Gateway: Integration

        # PUT:

        api_integration_put = aws_apigateway.AwsIntegration(service='dynamodb',
                                                            action='PutItem',
                                                            options=aws_apigateway.IntegrationOptions(
                                                                credentials_role=role,
                                                                passthrough_behavior=aws_apigateway.PassthroughBehavior.NEVER,
                                                                request_templates={
                                                                    'application/json': json.dumps(
                                                                        {
                                                                            "TableName": table.table_name,
                                                                            "Item": {
                                                                                "application": {
                                                                                    "S": "$util.escapeJavaScript($input.path('$').application)"
                                                                                },
                                                                                "operation": {
                                                                                    "S": "$util.escapeJavaScript($input.path('$').operation)"
                                                                                },
                                                                                "current_media_time": {
                                                                                    "N": "$input.path('$').currentMediaTime"
                                                                                },
                                                                                "source_ip": {
                                                                                    "S": "$context.identity.sourceIp"
                                                                                },
                                                                                "user_agent": {
                                                                                    "S": "$context.identity.userAgent"
                                                                                },
                                                                                "created_at": {
                                                                                    "S": "$context.requestTime"
                                                                                }
                                                                            }
                                                                        }
                                                                    )
                                                                },
                                                                integration_responses=[
                                                                    aws_apigateway.IntegrationResponse(
                                                                        # We will set the response status code to 200
                                                                        status_code="200",
                                                                        response_templates={
                                                                            'application/json': json.dumps(
                                                                                {
                                                                                    "state": "Success",
                                                                                    "message": "Updated items.",
                                                                                }
                                                                            )
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                    aws_apigateway.IntegrationResponse(
                                                                        selection_pattern='.*400.*',
                                                                        # We will set the response status code to 400
                                                                        status_code="400",
                                                                        response_templates={
                                                                            'application/json': json.dumps(
                                                                                {
                                                                                    "state": "Fail",
                                                                                    "message": "Error, please contact the admin.",
                                                                                }
                                                                            )
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                    aws_apigateway.IntegrationResponse(
                                                                        selection_pattern='.*401.*',
                                                                        # We will set the response status code to 401
                                                                        status_code="401",
                                                                        response_templates={
                                                                            'application/json': json.dumps(
                                                                                {
                                                                                    "state": "Fail",
                                                                                    "message": "Error, please contact the admin.",
                                                                                }
                                                                            )
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                    aws_apigateway.IntegrationResponse(
                                                                        selection_pattern=".*403.*",
                                                                        # We will set the response status code to 403
                                                                        status_code="403",
                                                                        response_templates={
                                                                            'application/json': json.dumps(
                                                                                {
                                                                                    "state": "Fail",
                                                                                    "message": "Error, please contact the admin.",
                                                                                }
                                                                            )
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                    aws_apigateway.IntegrationResponse(
                                                                        selection_pattern=".*404.*",
                                                                        # We will set the response status code to 404
                                                                        status_code="404",
                                                                        response_templates={
                                                                            'application/json': json.dumps(
                                                                                {
                                                                                    "state": "Fail",
                                                                                    "message": "Error, please contact the admin.",
                                                                                }
                                                                            )
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                    aws_apigateway.IntegrationResponse(
                                                                        selection_pattern=".*413.*",
                                                                        # We will set the response status code to 413
                                                                        status_code="413",
                                                                        response_templates={
                                                                            'application/json': json.dumps(
                                                                                {
                                                                                    "state": "Fail",
                                                                                    "message": "Error, please contact the admin.",
                                                                                }
                                                                            )
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                    aws_apigateway.IntegrationResponse(
                                                                        selection_pattern=".*429.*",
                                                                        # We will set the response status code to 429
                                                                        status_code="429",
                                                                        response_templates={
                                                                            'application/json': json.dumps(
                                                                                {
                                                                                    "state": "Fail",
                                                                                    "message": "Error, please contact the admin.",
                                                                                }
                                                                            )
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                    aws_apigateway.IntegrationResponse(
                                                                        selection_pattern="5\d{2}",
                                                                        # We will set the response status code to 500
                                                                        status_code="500",
                                                                        response_templates={
                                                                            'application/json': json.dumps(
                                                                                {
                                                                                    "state": "Fail",
                                                                                    "message": "Error, please contact the admin.",
                                                                                }
                                                                            )
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                ]
                                                            )
                                                            )

        # POST:

        api_integration_post = aws_apigateway.LambdaIntegration(function_post,
                                                                proxy=False,
                                                                request_templates={
                                                                    'application/json': json.dumps(
                                                                        {
                                                                            "start_date": "$util.escapeJavaScript($input.path('$').startDate)",
                                                                            "end_date": "$util.escapeJavaScript($input.path('$').endDate)",
                                                                            "application": "$util.escapeJavaScript($input.path('$').application)",
                                                                        }
                                                                    )
                                                                },
                                                                # This parameter defines the behavior of the engine is no suitable response template is found
                                                                passthrough_behavior=aws_apigateway.PassthroughBehavior.NEVER,
                                                                integration_responses=[
                                                                    aws_apigateway.IntegrationResponse(
                                                                        # We will set the response status code to 200
                                                                        status_code="200",
                                                                        response_templates={
                                                                            'application/json': "{\"counts\":$util.parseJson($input.json('$.response'))}"
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                    aws_apigateway.IntegrationResponse(
                                                                        # Java pattern style regex only.
                                                                        # https://docs.oracle.com/javase/8/docs/api/java/util/regex/Pattern.html
                                                                        selection_pattern=".*ValidationException.*",
                                                                        # We will set the response status code to 400
                                                                        status_code="400",
                                                                        response_templates={
                                                                            'application/json': """ {"state": "Fail","message": "$util.parseJson($input.path('$.errorMessage')).message"} """
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    ),
                                                                    aws_apigateway.IntegrationResponse(
                                                                        selection_pattern="(\n|.)+",
                                                                        # We will set the response status code to 500
                                                                        status_code="500",
                                                                        response_templates={
                                                                            'application/json': json.dumps(
                                                                                {
                                                                                    "state": "Fail",
                                                                                    "message": "Error, please contact the admin.",
                                                                                }
                                                                            )
                                                                        },
                                                                        response_parameters={
                                                                            # We can map response parameters
                                                                            'method.response.header.Content-Type': "'application/json'",
                                                                            'method.response.header.Access-Control-Allow-Origin': "'*'",
                                                                            'method.response.header.Access-Control-Allow-Credentials': "'true'"
                                                                        }
                                                                    )
                                                                ]
                                                                )

        # [ CREATE ] API Gateway: Model

        api_model_request_put = api.add_model('PUTRequestModel',
                                              content_type='application/json',
                                              model_name='PUTRequestModel',
                                              schema=aws_apigateway.JsonSchema(
                                                  schema=aws_apigateway.JsonSchemaVersion.DRAFT4,
                                                  title='PUTRequestModel',
                                                  type=aws_apigateway.JsonSchemaType.OBJECT,
                                                  # The parameters properties like type and character length.
                                                  properties={
                                                      'application': aws_apigateway.JsonSchema(
                                                          type=aws_apigateway.JsonSchemaType.STRING,
                                                          min_length=1
                                                      ),
                                                      'operation': aws_apigateway.JsonSchema(
                                                          type=aws_apigateway.JsonSchemaType.STRING,
                                                          min_length=1
                                                      ),
                                                      'currentMediaTime': aws_apigateway.JsonSchema(
                                                          type=aws_apigateway.JsonSchemaType.NUMBER,
                                                          min_length=1,
                                                      ),
                                                  },
                                                  # The parameters that are required to be submitted
                                                  required=[
                                                      'application',
                                                      'operation',
                                                      'currentMediaTime',
                                                  ]
                                              )
                                              )

        api_model_request_post = api.add_model('POSTRequestModel',
                                               content_type='application/json',
                                               model_name='POSTRequestModel',
                                               schema=aws_apigateway.JsonSchema(
                                                   schema=aws_apigateway.JsonSchemaVersion.DRAFT4,
                                                   title='POSTRequestModel',
                                                   type=aws_apigateway.JsonSchemaType.OBJECT,
                                                   # The parameters properties like type and character length.
                                                   properties={
                                                       'startDate': aws_apigateway.JsonSchema(
                                                           type=aws_apigateway.JsonSchemaType.STRING,
                                                           min_length=1
                                                       ),
                                                       'endDate': aws_apigateway.JsonSchema(
                                                           type=aws_apigateway.JsonSchemaType.STRING,
                                                           min_length=1
                                                       ),
                                                       'application': aws_apigateway.JsonSchema(
                                                           type=aws_apigateway.JsonSchemaType.STRING,
                                                           min_length=1,
                                                       ),
                                                   },
                                                   # The parameters that are required to be submitted
                                                   required=[
                                                       'startDate',
                                                       'endDate',
                                                       'application',
                                                   ]
                                               )
                                               )

        api_model_response_put = api.add_model('PUTResponseModel',
                                               content_type='application/json',
                                               model_name='PUTResponseModel',
                                               schema=aws_apigateway.JsonSchema(
                                                   schema=aws_apigateway.JsonSchemaVersion.DRAFT4,
                                                   title='PUTResponseModel',
                                                   type=aws_apigateway.JsonSchemaType.OBJECT,
                                                   properties={
                                                       'state': aws_apigateway.JsonSchema(
                                                           type=aws_apigateway.JsonSchemaType.STRING
                                                       ),
                                                       'message': aws_apigateway.JsonSchema(
                                                           type=aws_apigateway.JsonSchemaType.STRING
                                                       ),
                                                   }
                                               )
                                               )

        api_model_response_post = api.add_model('POSTResponseModel',
                                                content_type='application/json',
                                                model_name='POSTResponseModel',
                                                schema=aws_apigateway.JsonSchema(
                                                    schema=aws_apigateway.JsonSchemaVersion.DRAFT4,
                                                    title='POSTResponseModel',
                                                    type=aws_apigateway.JsonSchemaType.OBJECT,
                                                    properties={
                                                        'counts': aws_apigateway.JsonSchema(
                                                            type=aws_apigateway.JsonSchemaType.OBJECT
                                                        )
                                                    }
                                                )
                                                )

        api_model_response_error = api.add_model('ErrorResponseModel',
                                                 content_type='application/json',
                                                 model_name='ErrorResponseModel',
                                                 schema=aws_apigateway.JsonSchema(
                                                     schema=aws_apigateway.JsonSchemaVersion.DRAFT4,
                                                     title='ErrorResponseModel',
                                                     type=aws_apigateway.JsonSchemaType.OBJECT,
                                                     properties={
                                                         'state': aws_apigateway.JsonSchema(
                                                             type=aws_apigateway.JsonSchemaType.STRING
                                                         ),
                                                         'message': aws_apigateway.JsonSchema(
                                                             type=aws_apigateway.JsonSchemaType.STRING
                                                         ),
                                                     }
                                                 )
                                                 )

        # [ ADD ] API Gateway: Resource: Method:

        # PUT:

        api_resource_applications.add_method('PUT', api_integration_put,
                                             request_validator=api_validator_request,
                                             request_models={
                                                 'application/json': api_model_request_put
                                             },
                                             method_responses=[
                                                 aws_apigateway.MethodResponse(
                                                     # Successful response from the integration
                                                     status_code='200',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_put
                                                     }
                                                 ),
                                                 aws_apigateway.MethodResponse(
                                                     # Failed response from the integration
                                                     status_code='400',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_error
                                                     }
                                                 ),
                                                 aws_apigateway.MethodResponse(
                                                     # Failed response from the integration
                                                     status_code='401',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_error
                                                     }
                                                 ),
                                                 aws_apigateway.MethodResponse(
                                                     # Failed response from the integration
                                                     status_code='403',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_error
                                                     }
                                                 ),
                                                 aws_apigateway.MethodResponse(
                                                     # Failed response from the integration
                                                     status_code='404',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_error
                                                     }
                                                 ),
                                                 aws_apigateway.MethodResponse(
                                                     # Failed response from the integration
                                                     status_code='413',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_error
                                                     }
                                                 ),
                                                 aws_apigateway.MethodResponse(
                                                     # Failed response from the integration
                                                     status_code='429',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_error
                                                     }
                                                 ),
                                                 aws_apigateway.MethodResponse(
                                                     # Failed response from the integration
                                                     status_code='500',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_error
                                                     }
                                                 )
                                             ]
                                             )

        # POST:

        api_resource_applications.add_method('POST', api_integration_post,
                                             request_validator=api_validator_request,
                                             request_models={
                                                 'application/json': api_model_request_post
                                             },
                                             method_responses=[
                                                 aws_apigateway.MethodResponse(
                                                     # Successful response from the integration
                                                     status_code='200',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_post
                                                     }
                                                 ),
                                                 aws_apigateway.MethodResponse(
                                                     # Failed response from the integration
                                                     status_code='400',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_error
                                                     }
                                                 ),
                                                 aws_apigateway.MethodResponse(
                                                     # Failed response from the integration
                                                     status_code='500',
                                                     # Define what parameters are allowed or not
                                                     response_parameters={
                                                         'method.response.header.Content-Type': True,
                                                         'method.response.header.Access-Control-Allow-Origin': True,
                                                         'method.response.header.Access-Control-Allow-Credentials': True
                                                     },
                                                     # Validate the schema on the response
                                                     response_models={
                                                         'application/json': api_model_response_error
                                                     }
                                                 )
                                             ]
                                             )

        # [ CREATE ] CloudWatch: Metric:

        # TODO:: Replace dimensions.name with dynamic var.

        metric_api_gateway_error_4xx = aws_cloudwatch.Metric(
            namespace='AWS/ApiGateway',
            metric_name='4XXError',
            dimensions={
                'ApiName': 'api_application_metrics'
            }
        )

        metric_api_gateway_error_5xx = aws_cloudwatch.Metric(
            namespace='AWS/ApiGateway',
            metric_name='5XXError',
            dimensions={
                'ApiName': 'api_application_metrics'
            }
        )

        metric_lambda_error_log = aws_cloudwatch.Metric(
            namespace='Lambdas',
            metric_name='LambdaErrors',
        )

        metric_lambda_memory = aws_cloudwatch.Metric(
            namespace='Lambdas',
            metric_name='LambdaMemory',
        )

        # [ CREATE ] CloudWatch: Alarm:

        alarm_lambda_log_error = aws_cloudwatch.Alarm(self, 'LambdaLogError',
                                                      metric=metric_lambda_error_log,
                                                      alarm_description='Looks for logs reported as errors and reports if any is found.',
                                                      threshold=0,
                                                      evaluation_periods=1,
                                                      comparison_operator=aws_cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                                                      period=core.Duration.seconds(60),
                                                      actions_enabled=True,
                                                      treat_missing_data=aws_cloudwatch.TreatMissingData.NOT_BREACHING
                                                      )

        alarm_lambda_log_memory = aws_cloudwatch.Alarm(self, 'LambdaLogMemory',
                                                       metric=metric_lambda_memory,
                                                       alarm_description='Reads memory usage in MB reported in logs and reports if too high.',
                                                       threshold=110,
                                                       evaluation_periods=1,
                                                       comparison_operator=aws_cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                                                       period=core.Duration.seconds(60),
                                                       actions_enabled=True,
                                                       treat_missing_data=aws_cloudwatch.TreatMissingData.NOT_BREACHING,
                                                       statistic='Maximum'
                                                       )

        alarm_lambda_duration = aws_cloudwatch.Alarm(self, 'LambdaDuration',
                                                     metric=function_post.metric_duration(),
                                                     alarm_description='Uses AWS metrics to graph duration for the Lambda function.',
                                                     threshold=1000,
                                                     period=core.Duration.seconds(60),
                                                     evaluation_periods=1,
                                                     comparison_operator=aws_cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                                                     actions_enabled=True,
                                                     treat_missing_data=aws_cloudwatch.TreatMissingData.IGNORE,
                                                     statistic='Maximum'
                                                     )

        alarm_lambda_error = aws_cloudwatch.Alarm(self, 'LambdaError',
                                                  metric=function_post.metric_errors(),
                                                  alarm_description='Uses AWS metrics to count errors for the Lambda function.',
                                                  threshold=0,
                                                  period=core.Duration.seconds(60),
                                                  evaluation_periods=1,
                                                  comparison_operator=aws_cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                                                  actions_enabled=True,
                                                  treat_missing_data=aws_cloudwatch.TreatMissingData.NOT_BREACHING,
                                                  statistic='Maximum'
                                                  )

        alarm_api_gateway_error_4xx = aws_cloudwatch.Alarm(self, 'ApiGateway4XXError',
                                                           metric=metric_api_gateway_error_4xx,
                                                           threshold=0,
                                                           period=core.Duration.seconds(60),
                                                           evaluation_periods=1,
                                                           comparison_operator=aws_cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                                                           actions_enabled=True,
                                                           treat_missing_data=aws_cloudwatch.TreatMissingData.NOT_BREACHING,
                                                           )

        alarm_api_gateway_error_5xx = aws_cloudwatch.Alarm(self, 'ApiGateway5XXError',
                                                           metric=metric_api_gateway_error_5xx,
                                                           threshold=0,
                                                           period=core.Duration.seconds(60),
                                                           evaluation_periods=1,
                                                           comparison_operator=aws_cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                                                           actions_enabled=True,
                                                           treat_missing_data=aws_cloudwatch.TreatMissingData.NOT_BREACHING,
                                                           )

        # [ CREATE ] CloudWatch: Dashboard:

        dashboard_api = aws_cloudwatch.Dashboard(self, "ApiGateway")

        dashboard_lambda = aws_cloudwatch.Dashboard(self, "LambdaPOST")

        # [ ADD ] CloudWatch: Dashboard: Widgets

        dashboard_api.add_widgets(
            aws_cloudwatch.GraphWidget(
                title="HTTP Errors",
                width=24,
                left=[
                    metric_api_gateway_error_4xx.with_(
                        color="#ff8000",
                    ),
                    metric_api_gateway_error_5xx.with_(
                        color="#ff4d4d",
                    ),
                ]
            ),
        )

        dashboard_api.add_widgets(
            aws_cloudwatch.AlarmWidget(
                title='4xxErrorAlarms',
                alarm=alarm_api_gateway_error_4xx,
                width=12
            ),
            aws_cloudwatch.AlarmWidget(
                title='5xxErrorAlarms',
                alarm=alarm_api_gateway_error_5xx,
                width=12,
            ),
        )

        dashboard_lambda.add_widgets(
            aws_cloudwatch.SingleValueWidget(
                width=24,
                metrics=[
                    function_post.metric_invocations().with_(
                        color="#0052cc"
                    ),
                    function_post.metric_errors().with_(
                        color="#ff3333"
                    ),
                    function_post.metric_throttles().with_(
                        color="#ffff1a"
                    ),
                    function_post.metric_duration().with_(
                        label="Duration (max)",
                        color="#5cd65c",
                        statistic="Maximum",
                    ),
                    metric_lambda_memory.with_(
                        label="Memory (max)",
                        color="#ff8000",
                        statistic="Maximum",
                    ),
                ]
            ),
        )

        dashboard_lambda.add_widgets(
            aws_cloudwatch.GraphWidget(
                title="Error",
                width=6,
                left=[
                    function_post.metric_errors().with_(
                        label="Errors",
                        color="#ff4d4d",
                    ),
                ],
            ),
            aws_cloudwatch.GraphWidget(
                title="LogError",
                width=6,
                left=[
                    metric_lambda_error_log.with_(
                        label="Errors",
                        color="#ff4d4d",
                    ),
                ],
            ),
            aws_cloudwatch.GraphWidget(
                title="Memory",
                width=6,
                left=[
                    metric_lambda_memory.with_(
                        label="Maximum",
                        color="#ff4d4d",
                        statistic="Maximum"
                    ),
                    metric_lambda_memory.with_(
                        label="Minimum",
                        color="#5cd65c",
                        statistic="Minimum"
                    ),
                    metric_lambda_memory.with_(
                        label="Average",
                        color="#ff8000",
                        statistic="Average"
                    ),
                ],
            ),
            aws_cloudwatch.GraphWidget(
                title="Duration",
                width=6,
                left=[
                    function_post.metric_duration().with_(
                        label="Maximum",
                        color="#ff4d4d",
                        statistic="Maximum"
                    ),
                    function_post.metric_duration().with_(
                        label="Minimum",
                        color="#5cd65c",
                        statistic="Minimum"
                    ),
                    function_post.metric_duration().with_(
                        label="Average",
                        color="#ff8000",
                        statistic="Average"
                    ),
                ],
            ),
        )

        dashboard_lambda.add_widgets(
            aws_cloudwatch.AlarmWidget(
                title='ErrorAlarms',
                alarm=alarm_lambda_error,
                width=6
            ),
            aws_cloudwatch.AlarmWidget(
                title='LogErrorAlarms',
                alarm=alarm_lambda_log_error,
                width=6,
            ),
            aws_cloudwatch.AlarmWidget(
                title='MemoryAlarms',
                alarm=alarm_lambda_log_memory,
                width=6
            ),
            aws_cloudwatch.AlarmWidget(
                title='DurationAlarms',
                alarm=alarm_lambda_duration,
                width=6,
            ),
        )

        # [ CREATE ] SNS: Topic:

        topic = aws_sns.Topic(self, 'Errors')

        # [ CREATE ] SNS: Subscription:

        for email in notification_emails:
            topic.add_subscription(
                aws_sns_subscriptions.EmailSubscription(
                    email_address=email
                )
            )

        # [ CREATE ] CloudWatch: Action:

        action = aws_cloudwatch_actions.SnsAction(
            topic=topic
        )

        # [ ADD ] Log: Alarm: Action:

        alarm_lambda_log_error.add_alarm_action(action)

        alarm_lambda_log_memory.add_alarm_action(action)

        alarm_lambda_duration.add_alarm_action(action)

        alarm_api_gateway_error_5xx.add_alarm_action(action)
