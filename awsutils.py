import boto3
import subprocess
import json
import time


def set_aws_credentials(profile, region_name='us-east-1'):
    result = subprocess.run(
        f"aws-vault exec {profile} --json", shell=True, capture_output=True)
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


def exact_date(year, month, day) -> int:
    return int(time.mktime((year, month, day, 0, 0, 0, 0, 0, 0)))


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
    query_id = execute_query(logs_client, log_group, query, start_time, end_time)
    wait_for_query(logs_client, query_id)
    response, records_scanned, records_matched = get_query_results(logs_client, query_id)
    print (f'records_scanned: {records_scanned}')
    print (f'records_matched: {records_matched}')

    # Flatten the data
    data = []
    for entry in response:
        row = {item['field']: item['value'] for item in entry}
        data.append(row)
    return data


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

