#!/bin/bash

if [ "$1" == "" ]; then
  echo "usage: $0 <task-id>"
  exit -1
fi

task_id=$1

AWS_PROFILE=vibe-dev aws ecs execute-command --cluster shoss-promotion-dev --task $task_id --container promotion --interactive --command /bin/bash --region us-east-1

exit $?

