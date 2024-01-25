#!/bin/bash

# Assuming aws-vault is configured and available

# Accept log group name and log stream prefix as arguments
AWS_PROFILE=$1
AWS_REGION=$2
LOG_GROUP_NAME=$3
LOG_STREAM_PREFIX=$4

# Execute the AWS command with the provided arguments
aws-vault exec $AWS_PROFILE --region $AWS_REGION -- aws logs describe-log-streams --log-group-name $LOG_GROUP_NAME --log-stream-name-prefix $LOG_STREAM_PREFIX
