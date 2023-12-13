Attaching to a running task in AWS:

`aws-vault exec acl-playground --region=us-west-2 -- aws ecs execute-command --cluster EcsCluster1-main --task ebe41d4d34ac472e9b7965efa5e387af --command "/bin/bash" --interactive --container nginx`