#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab

import aws_cdk as cdk

from aws_cdk import (
  Stack,
  aws_iam
)
from constructs import Construct


class FirehoseRoleStack(Stack):

  def __init__(self, scope: Construct, construct_id: str,
               data_transform_lambda_fn, source_kinesis_stream, s3_bucket,
               **kwargs) -> None:

    super().__init__(scope, construct_id, **kwargs)

    data_firehose_configuration = self.node.try_get_context("data_firehose_configuration")

    firehose_stream_name = data_firehose_configuration["stream_name"]

    firehose_role_policy_doc = aws_iam.PolicyDocument()

    firehose_role_policy_doc.add_statements(aws_iam.PolicyStatement(
      effect=aws_iam.Effect.ALLOW,
      resources=[source_kinesis_stream.stream_arn],
      actions=[
        "kinesis:DescribeStream",
        "kinesis:GetShardIterator",
        "kinesis:GetRecords",
        "kinesis:ListShards"
      ]
    ))

    firehose_role_policy_doc.add_statements(aws_iam.PolicyStatement(**{
      "effect": aws_iam.Effect.ALLOW,
      "resources": [s3_bucket.bucket_arn, "{}/*".format(s3_bucket.bucket_arn)],
      "actions": [
        "s3:AbortMultipartUpload",
        "s3:GetBucketLocation",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:ListBucketMultipartUploads",
        "s3:PutObject",
        "s3:DeleteObject"
      ]
    }))

    firehose_role_policy_doc.add_statements(aws_iam.PolicyStatement(**{
      "effect": aws_iam.Effect.ALLOW,
      "resources": [
        f"arn:aws:glue:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:catalog",
        f"arn:aws:glue:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:database/*",
        f"arn:aws:glue:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:table/*/*"
      ],
      "actions": [
        "glue:GetTable",
        "glue:GetDatabase",
        "glue:UpdateTable"
      ]
    }))

    firehose_role_policy_doc.add_statements(aws_iam.PolicyStatement(
      effect=aws_iam.Effect.ALLOW,
      resources=["*"],
      actions=[
        "ec2:DescribeVpcs",
        "ec2:DescribeVpcAttribute",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeNetworkInterfaces",
        "ec2:CreateNetworkInterface",
        "ec2:CreateNetworkInterfacePermission",
        "ec2:DeleteNetworkInterface"
      ]
    ))

    #XXX: https://docs.aws.amazon.com/ko_kr/cdk/latest/guide/tokens.html
    # String-encoded tokens:
    #  Avoid manipulating the string in other ways. For example,
    #  taking a substring of a string is likely to break the string token.
    firehose_log_group_name = f"/aws/kinesisfirehose/{firehose_stream_name}"
    firehose_role_policy_doc.add_statements(aws_iam.PolicyStatement(
      effect=aws_iam.Effect.ALLOW,
      #XXX: The ARN will be formatted as follows:
      # arn:{partition}:{service}:{region}:{account}:{resource}{sep}}{resource-name}
      resources=[self.format_arn(service="logs", resource="log-group",
        resource_name="{}:log-stream:*".format(firehose_log_group_name),
        arn_format=cdk.ArnFormat.COLON_RESOURCE_NAME)],
      actions=["logs:PutLogEvents"]
    ))

    firehose_role_policy_doc.add_statements(aws_iam.PolicyStatement(**{
      "effect": aws_iam.Effect.ALLOW,
      "resources": [f"{data_transform_lambda_fn.function_arn}:*"],
      "actions": [
        "lambda:InvokeFunction",
        "lambda:GetFunctionConfiguration"
      ]
    }))

    self.firehose_role = aws_iam.Role(self, "KinesisFirehoseServiceRole",
      role_name="KinesisFirehoseServiceRole-{stream_name}-{region}".format(
        stream_name=firehose_stream_name, region=cdk.Aws.REGION),
      assumed_by=aws_iam.ServicePrincipal("firehose.amazonaws.com"),
      #XXX: use inline_policies to work around https://github.com/aws/aws-cdk/issues/5221
      inline_policies={
        "firehose_role_policy": firehose_role_policy_doc
      }
    )


    cdk.CfnOutput(self, 'FirehoseRole',
      value=self.firehose_role.role_name,
      export_name=f'{self.stack_name}-Role')
    cdk.CfnOutput(self, 'FirehoseRoleArn',
      value=self.firehose_role.role_arn,
      export_name=f'{self.stack_name}-RoleArn')