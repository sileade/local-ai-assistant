'''# Monitoring and Logging Guide

This guide provides instructions for setting up a comprehensive, self-hosted monitoring and logging stack using Prometheus, Grafana, and Loki, as per user preferences. This stack provides deep insights into system and application performance.

## 1. Architecture Overview

- **Prometheus**: Scrapes and stores time-series data (metrics) from configured endpoints.
- **Loki**: Aggregates and stores log data from various sources.
- **Grafana**: Visualizes data from both Prometheus (metrics) and Loki (logs) in a unified dashboard.
- **Promtail**: An agent that ships logs from local files to a Loki instance.

We will use Docker Compose to orchestrate these services.

## 2. Setup and Configuration

Use the `docker-compose.monitoring.yml` template located in the `templates/` directory of this skill. This file defines the services for Grafana, Loki, and Prometheus.

**Step 1: Create Configuration Files**

Before starting the stack, create the necessary configuration files.

- **Prometheus (`templates/prometheus.yml`):** This file defines which endpoints Prometheus should scrape. The template includes scraping Prometheus itself and Loki.
- **Loki (`templates/loki-config.yml`):** Configures Loki, including the storage location for logs.
- **Promtail (`templates/promtail-config.yml`):** Configures Promtail to read logs from specific directories (e.g., `/var/log`) and send them to Loki.

**Step 2: Deploy the Monitoring Stack**

1.  Copy the template files to a dedicated monitoring directory (e.g., `/opt/monitoring`).
2.  Modify the configuration files as needed (e.g., add new scrape targets to `prometheus.yml`).
3.  Start the stack using Docker Compose:
    ```bash
    cd /opt/monitoring
    docker-compose -f docker-compose.monitoring.yml up -d
    ```

## 3. Accessing the Services

- **Grafana**: `http://<your-server-ip>:3000` (default user/pass: admin/admin)
- **Prometheus**: `http://<your-server-ip>:9090`
- **Loki**: Accessible via Grafana data source.

## 4. Configuring Grafana

After the first login to Grafana, you will be prompted to change the password.

**Step 1: Add Data Sources**

1.  Navigate to **Configuration > Data Sources**.
2.  Add a **Prometheus** data source, pointing to `http://prometheus:9090`.
3.  Add a **Loki** data source, pointing to `http://loki:3100`.

**Step 2: Create a Dashboard**

You can now create dashboards to visualize your data.

- **Metrics**: Create panels using the Prometheus data source to plot metrics over time (e.g., CPU usage, memory, network I/O).
- **Logs**: Create panels using the Loki data source to display and query logs. You can use LogQL to filter and search logs (e.g., `{job="varlogs"} |= "error"`).

## 5. Automated Incident Diagnosis

With this stack, the assistant can perform automated incident diagnosis.

**Example Request:**
> "Our web application is slow. Investigate the issue."

**Workflow:**
1.  **Assistant:** Queries Prometheus for key application and system metrics (e.g., `http_requests_total`, `cpu_usage`, `memory_usage`) over the last hour to identify anomalies.
2.  **Assistant:** If a spike in errors or resource usage is found, it correlates the timestamp with logs in Loki.
3.  **Assistant:** Queries Loki for logs around the time of the incident (e.g., `_`json {job="webapp"} |~ "error|exception" and time > now() - 1h`_`).
4.  **Assistant:** Analyzes the logs and metrics to form a hypothesis about the root cause (e.g., "A spike in 500 errors correlates with a database connection error in the logs.").
5.  **Assistant:** Reports the findings and suggested next steps to the user.
'''
