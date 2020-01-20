from aws_cdk import (
    core,
    aws_dynamodb,
    aws_lambda,
)


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
