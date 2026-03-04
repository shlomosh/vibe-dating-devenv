# Running AWS Lambda Docker Containers

This document explains how to run AWS Lambda Docker containers for local development and testing.

## Quick Start

To run an AWS Lambda Python 3.11 container interactively:

```bash
docker run -it --entrypoint "" public.ecr.aws/lambda/python:3.11 /bin/bash
```

## Command Breakdown

- `docker run`: Creates and starts a new container
- `-it`: Interactive mode with pseudo-TTY allocation
- `--entrypoint ""`: Overrides the default entrypoint to run a custom command
- `public.ecr.aws/lambda/python:3.11`: Official AWS Lambda Python 3.11 runtime image
- `/bin/bash`: Starts a bash shell instead of the default Lambda handler

## Use Cases

This approach is useful for:

- **Local Development**: Testing Lambda functions in a containerized environment
- **Debugging**: Investigating issues with Lambda runtime dependencies
- **Dependency Testing**: Verifying package compatibility with the Lambda environment
- **Environment Consistency**: Ensuring your code works in the same environment as AWS Lambda

## Alternative Commands

### Run with specific working directory:
```bash
docker run -it --entrypoint "" -v $(pwd):/var/task public.ecr.aws/lambda/python:3.11 /bin/bash
```

### Run with port mapping (for API Gateway testing):
```bash
docker run -it --entrypoint "" -p 9000:8080 public.ecr.aws/lambda/python:3.11 /bin/bash
```

### Run with environment variables:
```bash
docker run -it --entrypoint "" -e AWS_REGION=us-east-1 public.ecr.aws/lambda/python:3.11 /bin/bash
```

## Next Steps

Once inside the container:

1. Install additional dependencies: `pip install <package-name>`
2. Test your Lambda function code
3. Verify environment variables and configuration
4. Exit with `exit` or `Ctrl+D`

## Related Documentation

- [AWS Lambda Docker Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Lambda Runtime Interface](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-api.html)
- [Local Testing with Docker](https://docs.aws.amazon.com/lambda/latest/dg/images-test.html)