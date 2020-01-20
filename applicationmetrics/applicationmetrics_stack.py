from aws_cdk import (
    core,
    aws_apigateway,
    aws_dynamodb,
    aws_lambda,
    aws_iam,
)

import json


class ApplicationmetricsStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

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
                                            code=aws_lambda.Code.asset('./lambdas/applications')
                                            )

        # [ CREATE ] DynamoDB: Permission:

        table.grant_read_data(function_post)

        # [ CREATE ] Lambda: Environment:

        function_post.add_environment('TABLE_NAME', table.table_name)

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

        api_resource_students = api.root.add_resource('applications')

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
                                                                                    "S": "$input.path('$').currentMediaTime"
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
                                                                    )
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
                                                                        selection_pattern=".*UnknownException.*",
                                                                        # We will set the response status code to 500
                                                                        status_code="500",
                                                                        response_templates={
                                                                            'application/json': """ {"state": "Fail","message": "$util.parseJson($input.path('$.errorMessage')).message"} """
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

        api_resource_students.add_method('PUT', api_integration_put,
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
                                             )
                                         ]
                                         )

        # POST:

        api_resource_students.add_method('POST', api_integration_post,
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
