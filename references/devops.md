'''# DevOps Engineer Guide

This guide provides advanced workflows for DevOps practices, enabling the assistant to manage infrastructure, automate deployments, and orchestrate containers.

## 1. Infrastructure as Code (IaC)

The assistant can manage cloud infrastructure using tools like Terraform and Ansible. This involves writing, planning, and applying configuration files.

**Example Request:**
> "Создай новый t3.micro EC2 инстанс в AWS с помощью Terraform. Используй регион us-east-1 и последний AMI для Ubuntu 22.04."

**Workflow:**
1.  **User:** Specifies the desired infrastructure.
2.  **Assistant:** Writes a Terraform configuration file (`main.tf`) using the `file` tool.
    ```terraform
    provider "aws" {
      region = "us-east-1"
    }

    data "aws_ami" "ubuntu" {
      most_recent = true
      filter {
        name   = "name"
        values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
      }
      owners = ["099720109477"] # Canonical
    }

    resource "aws_instance" "web" {
      ami           = data.aws_ami.ubuntu.id
      instance_type = "t3.micro"

      tags = {
        Name = "WebApp-Server"
      }
    }
    ```
3.  **Assistant:** Executes Terraform commands using the `shell` tool.
    ```bash
    terraform init
    terraform plan
    # Asks user for confirmation before applying
    terraform apply -auto-approve
    ```
4.  **Assistant:** Reports the outcome and any outputs (like the instance IP address).

## 2. CI/CD Pipelines

The assistant can define and manage CI/CD pipelines, for example, using GitHub Actions.

**Example Request:**
> "Настрой простой CI/CD пайплайн для моего Python-проекта. Он должен запускать тесты при каждом пуше в main и, в случае успеха, собирать Docker-образ и пушить его в Docker Hub."

**Workflow:**
1.  **User:** Describes the desired CI/CD process.
2.  **Assistant:** Creates a GitHub Actions workflow file (`.github/workflows/ci.yml`) using the `file` tool.
3.  **Assistant:** The YAML file will contain steps for checking out code, setting up Python, running tests, logging into Docker Hub (using secrets), building the image, and pushing it.
4.  **Assistant:** Guides the user on where to place the file in their repository and how to configure the necessary secrets (e.g., `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`).

## 3. Container & Kubernetes Management

The assistant can manage Docker containers and Kubernetes deployments.

**Example Request (Kubernetes):**
> "Разверни этот Docker-образ `my-app:latest` в нашем Kubernetes-кластере. Создай Deployment с 3 репликами и Service типа LoadBalancer."

**Workflow:**
1.  **User:** Provides the Docker image and deployment requirements.
2.  **Assistant:** Writes a Kubernetes manifest file (`deployment.yaml`) using the `file` tool.
3.  **Assistant:** The manifest will define a `Deployment` and a `Service` resource.
4.  **Assistant:** Applies the manifest to the cluster using `kubectl` via the `shell` tool.
    ```bash
    kubectl apply -f deployment.yaml
    ```
5.  **Assistant:** Checks the status of the deployment and service and reports back to the user.
    ```bash
    kubectl get deployments
    kubectl get services
    ```
'''
