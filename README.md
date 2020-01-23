# cdk-api-gateway-lambda-dynamo

An AWS CDK construct which exposes two public HTTP endpoints. The first endpoint for writing data 
directly to a DynamoDB table with a service integration. The second for reading data from the 
table with a Lambda integration.

X-Ray and CloudWatch metrics are used to monitor the resources with alarms attached to the metrics in conjunction
with SNS to send alerts by email. Dashboards for monitoring details.

### Services

| Name  | Description |
| ------------- | ------------- |
| API Gateway  | Handling requests and responses  |
| Lambda | Reading storage and converting output  |
| DynamoDB | Storage |
| CloudWatch | Health monitoring & Logs |
| SNS | Alerting for issues |
| X-Ray | Health monitoring |

# Usage

### CFN

The template comes included with all assets. It's ready to deploy.

```
cloud_formation_template.yaml
```

### CDK

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project.  The initialization process also creates
a virtualenv within this project, stored under the .env directory.  To create the virtualenv
it assumes that there is a `python3` executable in your path with access to the `venv` package.
If for any reason the automatic creation of the virtualenv fails, you can create the virtualenv
manually once the init process completes.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .env
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .env/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .env\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

Open `applicationmetrics_stack.py` and add emails to `notification_emails` list to receive alarm notifications.

```
$ vim applicationmetrics/applicationmetrics_stack.py
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

You can now begin exploring the source code, contained in the hello directory.
There is also a very trivial test included that can be run like this:

```
$ pytest
```
You can deploy the stack to your AWS account.

```
$ cdk deploy
```

To add additional dependencies, for example other CDK libraries, just add to
your requirements.txt file and rerun the `pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation
 
## Useful links

* [Getting Started](https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html)
* [CDK Workshop](https://cdkworkshop.com/)

Enjoy!
