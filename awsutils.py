import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from botocore.exceptions import ClientError
import boto3
import pytz


def set_aws_credentials(profile, region_name='us-east-1'):
    result = subprocess.run(
        f"aws-vault exec {profile} --json", shell=True, capture_output=True, check=True)
    credentials = json.loads(result.stdout)

    # Create a session with the retrieved credentials
    session = boto3.session.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region_name
    )

    return session


def now() -> int:
    return int(time.time())


def hours_ago(hours) -> int:
    return int(time.time() - 60 * 60 * hours)


def days_ago(days) -> int:
    return int(time.time() - 60 * 60 * 24 * days)


def exact_date(year, month, day, hour = 0, minute = 0, second = 0) -> int:
    return int(time.mktime((year, month, day, hour, minute, second, 0, 0, 0)))


def execute_query(logs_client, log_group, query, start_time, end_time):
    response = logs_client.start_query(
        logGroupName=log_group,
        startTime=start_time,
        endTime=end_time,
        queryString=query,
    )
    return response['queryId']


def wait_for_query(logs_client, query_id):
    done = False
    while not done:
        stats = logs_client.get_query_results(queryId=query_id)
        status = stats['status']
        if status == 'Complete':
            print("Query completed.")
            done = True
        elif status == 'Running':
            print("Query still running...")
        elif status == 'Scheduled':
            print("Query scheduled...")
        else:
            print(f"Query status: {status}")
        time.sleep(1)

def get_query_results(logs_client, query_id):
    response = logs_client.get_query_results(queryId=query_id)
    return response['results'], int(response['statistics']['recordsScanned']), int(response['statistics']['recordsMatched'])


def cloudwatch_query(logs_client, log_group, query, start_time=hours_ago(1), end_time=now()):
    """
    Execute a CloudWatch Logs Insights query and return the results.
    This function executes a query against CloudWatch Logs, waits for completion,
    and returns either the flattened results or the count of matched records if
    the result set is too large (>=10000 records).
    Args:
        logs_client: boto3 CloudWatch Logs client
        log_group (str): The name of the log group to query
        query (str): The query string to execute
        start_time (int): Start time for the query in milliseconds since epoch (default: 1 hour ago)
        end_time (int): End time for the query in milliseconds since epoch (default: current time)
    Returns:
        Union[list[dict], int]: If records_matched < 10000, returns a list of dictionaries where each
                               dictionary represents a log entry with field-value pairs.
                               If records_matched >= 10000, returns the number of matched records.
    Example:
        >>> logs_client = boto3.client('logs')
        >>> results = cloudwatch_query(logs_client, '/aws/lambda/my-function',
                                     'fields @timestamp, @message | sort @timestamp desc')
    """
    query_id = execute_query(logs_client, log_group, query, start_time, end_time)
    wait_for_query(logs_client, query_id)
    response, records_scanned, records_matched = get_query_results(logs_client, query_id)
    print (f'records_scanned: {records_scanned}')
    print (f'records_matched: {records_matched}')

    if records_matched >= 10000:
        return records_matched
    
    # Flatten the data
    data = []
    for entry in response:
        row = {item['field']: item['value'] for item in entry}
        data.append(row)
    return data


def cloudwatch_crawler(logs_client, log_group, base_query, start_date, end_date, folder_name, slices=1):
    """
    Fetches log entries from CloudWatch Logs by splitting the time range into slices and querying in parallel.
    This function splits a given time range into smaller slices and queries CloudWatch Logs for each slice
    in parallel using a ThreadPoolExecutor. If a slice returns more than 10,000 records (the CloudWatch Logs limit),
    it recursively splits that slice into smaller pieces.
    Args:
        logs_client: Boto3 CloudWatch Logs client
        log_group (str): Name of the CloudWatch Logs log group to query
        base_query (str): Base query string to execute against CloudWatch Logs
        start_date (int): Start timestamp in epoch seconds
        end_date (int): End timestamp in epoch seconds
        folder_name (str): Name of folder where result files will be saved
        slices (int, optional): Number of time slices to split the query into. Defaults to 1.
    Returns:
        None: Results are written to JSON files in the specified folder
    Files are saved in the format: ./{folder_name}/{folder_name}_{start_timestamp}.json
    Note:
        - Maximum 10 concurrent queries are executed in parallel
        - Each query has a limit of 10,000 records
        - If a file for a time slice already exists, that slice is skipped
        - If a slice returns more than 10K records, it's automatically split into smaller slices
    """
    slice_duration = (end_date - start_date) / slices
    query = base_query + " | limit 10000"

    future_to_task = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for i in range(slices):
            # Calculate the start and end timestamps for the current time slice
            start_timestamp = int(start_date + (i * slice_duration))
            end_timestamp = int(start_date + ((i + 1) * slice_duration))
        
            # print time slice in human readable format (original format is epoch time in seconds)
            print(f"Time slice {i}: {datetime.fromtimestamp(start_timestamp, tz=pytz.timezone('UTC'))} - {datetime.fromtimestamp(end_timestamp, tz=pytz.timezone('UTC'))}")

            # create filename with slice number
            filename = f'./{folder_name}/{folder_name}_{start_timestamp}.json'

            # skip file if it already exists
            if os.path.exists(filename):
                print(f"File {filename} already exists. Skipping.")
                continue

            future_to_task.append((executor.submit(
                cloudwatch_query, logs_client, log_group, query, start_timestamp, end_timestamp), i, filename, start_timestamp, end_timestamp))
            
        for future, slice_num, filename, start_ts, end_ts in future_to_task:
            try:
                result = future.result()
                # if result contains more than 10K records, the returning type is integer
                if isinstance(result, int):
                    print(f"Slice {slice_num}: More than 10000 records found. Splitting the time slice.")
                    # Recursively fetch the further pieces
                    slices = int(result * 1.1) // 10000 + 1  # add 10% buffer
                    cloudwatch_crawler(logs_client, log_group, base_query, start_ts, end_ts, folder_name, slices=slices)
                else:
                    # print the number of log entries in each time slice
                    print(f"Slice {slice_num}: Number of log entries: {len(result)}")
                    # write results to file
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(result))
                        f.write('\n')
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    print("Session expired")
                else:
                    print("Unexpected error: %s" % e)


def parse_json_messages(data):
    # Parse the @message field in each entry
    for entry in data:
        message_json = entry["@message"]
        
        # Parse the JSON string in @message field
        try:
            message_data = json.loads(message_json)
        except:
            continue
        
        entry["@message"] = message_data



def get_tasks(ecs_client, cluster_name, service_name):
    # List all running tasks in a specified service
    response = ecs_client.list_tasks(
        cluster=cluster_name,
        serviceName=service_name,
        desiredStatus='RUNNING'
    )
    return response['taskArns']


def get_task_definition(ecs_client, cluster_name, task_arns):
    tasks = ecs_client.describe_tasks(cluster=cluster_name, tasks=task_arns)['tasks']

    if len(tasks) == 0:
        raise Exception("No tasks found")
    
    task_definition_arn = tasks[0]['taskDefinitionArn']

    response = ecs_client.describe_task_definition(taskDefinition=task_definition_arn)
    task_definition = response['taskDefinition']
    return task_definition


def get_container_definition(task_definition, container_name):
    for container_definition in task_definition['containerDefinitions']:
        if container_definition['name'] == container_name:
            return container_definition
    return None

