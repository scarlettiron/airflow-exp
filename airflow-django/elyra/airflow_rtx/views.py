import re
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class AirflowDagsView(APIView):
    """
    API endpoint to fetch DAGs from Apache Airflow using session authentication.
    Supports an 'offset' query parameter for pagination.
    """

    def get(self, request):
        # Airflow configuration
        airflow_url = 'http://localhost:8080'
        airflow_user = 'admin'
        airflow_password = 'admin'

        session = requests.Session()
        login_url = f"{airflow_url}/login/"

        # Step 1: Retrieve the login page
        login_page = session.get(login_url)
        if login_page.status_code != 200:
            return Response(
                {"error": "Unable to load Airflow login page."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Step 2: Extract CSRF token using a more robust regex
        csrf_token_match = re.search(
            r'<input[^>]*name=[\'"]csrf_token[\'"][^>]*value=[\'"]([^\'"]+)[\'"]',
            login_page.text
        )
        csrf_token = csrf_token_match.group(1) if csrf_token_match else None

        # Fallback: try to extract CSRF token from cookies (if set)
        if not csrf_token:
            csrf_token = session.cookies.get("csrf_token")

        # Prepare the login payload
        payload = {
            "username": airflow_user,
            "password": airflow_password,
        }
        if csrf_token:
            payload["csrf_token"] = csrf_token

        # Prepare headers: adding a Referer and sending the token in header may help
        headers = {"Referer": login_url}
        if csrf_token:
            headers["X-CSRFToken"] = csrf_token

        # Step 3: Authenticate by posting to the login endpoint
        login_response = session.post(login_url, data=payload, headers=headers)
        if login_response.status_code != 200:
            return Response(
                {"error": "Airflow login failed.", "details": login_response.text},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Step 4: With the authenticated session, fetch the DAGs
        dags_url = f"{airflow_url}/api/v1/dags"
        offset = request.GET.get("offset", 0)
        api_response = session.get(dags_url, params={
            "offset": offset,
            "order_by": "dag_id"
        })

        if api_response.status_code != 200:
            return Response(
                {"error": "Failed to fetch DAGs from Airflow."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(api_response.json(), status=status.HTTP_200_OK)
    








class AirflowDagLogsView(APIView):
    """
    API endpoint to retrieve all logs related to a specific DAG.
    Expects a query parameter 'dag_id'. It will:
      1. Login to Airflow using session authentication.
      2. Retrieve all DAG runs for the given dag_id.
      3. For each DAG run, retrieve task instances.
      4. For each task instance, fetch the log for its current try.
      
    The response is a nested JSON object:
      {
          "dag_id": <dag_id>,
          "logs": {
              "<dag_run_id>": {
                  "<task_id>": "<log text or error message>",
                  ...
              },
              ...
          }
      }
    """
    def get(self, request, dag_id, *args, **kwargs):

        if not dag_id:
            return Response(
                {"error": "dag_id parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Airflow configuration; these could also be stored in Django settings.
        airflow_url = 'http://localhost:8080'
        airflow_user = 'admin'
        airflow_password = 'admin'
        
        session = requests.Session()
        login_url = f"{airflow_url}/login/"
        
        # Step 1: Load the login page to grab the CSRF token
        login_page = session.get(login_url)
        if login_page.status_code != 200:
            return Response(
                {"error": "Unable to load Airflow login page."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Extract CSRF token using regex (handles both single/double quotes)
        csrf_token_match = re.search(
            r'<input[^>]*name=[\'"]csrf_token[\'"][^>]*value=[\'"]([^\'"]+)[\'"]',
            login_page.text
        )
        csrf_token = csrf_token_match.group(1) if csrf_token_match else None
        if not csrf_token:
            csrf_token = session.cookies.get("csrf_token")
        
        # Prepare login payload and headers
        payload = {
            "username": airflow_user,
            "password": airflow_password,
        }
        if csrf_token:
            payload["csrf_token"] = csrf_token
        
        headers = {"Referer": login_url}
        if csrf_token:
            headers["X-CSRFToken"] = csrf_token
        
        # Step 2: Authenticate with Airflow
        login_response = session.post(login_url, data=payload, headers=headers)
        if login_response.status_code != 200:
            return Response(
                {"error": "Airflow login failed.", "details": login_response.text},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Step 3: Retrieve all DAG runs for the given dag_id
        dag_runs_url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns"
        dag_runs_response = session.get(dag_runs_url)
        if dag_runs_response.status_code != 200:
            return Response(
                {"error": f"Failed to fetch DAG runs for dag_id {dag_id}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        dag_runs_data = dag_runs_response.json()
        dag_runs = dag_runs_data.get("dag_runs", [])
        
        # Prepare a container for logs.
        all_logs = {}
        
        # Step 4: For each dag run, get task instances and then each task log.
        for dag_run in dag_runs:
            run_id = dag_run.get("dag_run_id")
            task_instances_url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances"
            ti_response = session.get(task_instances_url)
            if ti_response.status_code != 200:
                continue  # Skip this dag run if unable to get its task instances.
            
            ti_data = ti_response.json()
            task_instances = ti_data.get("task_instances", [])
            run_logs = {}
            
            for task_instance in task_instances:
                task_id = task_instance.get("task_id")
                # Use the try_number if available, default to 1.
                try_number = task_instance.get("try_number", 1)
                log_url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}"
                log_response = session.get(log_url)
                if log_response.status_code == 200:
                    run_logs[task_id] = log_response.text
                else:
                    run_logs[task_id] = f"Error fetching log: {log_response.status_code}"
            all_logs[run_id] = run_logs
        
        return Response({"dag_id": dag_id, "logs": all_logs}, status=status.HTTP_200_OK)







class AirflowAllDagLogsView(APIView):
    """
    API endpoint to retrieve logs for all DAGs from Airflow.
    The endpoint performs the following steps:
      1. Authenticate with Airflow (using session and CSRF token).
      2. Retrieve the list of all DAGs.
      3. For each DAG, retrieve its DAG runs.
      4. For each DAG run, retrieve its task instances and fetch each log.
    
    The response is structured as:
      {
          "all_logs": {
              "<dag_id>": {
                  "<dag_run_id>": {
                      "<task_id>": "<log text or error message>",
                      ...
                  },
                  ...
              },
              ...
          }
      }
    """

    def get(self, request, *args, **kwargs):
        # Airflow configuration (these could also be stored in settings)
        airflow_url = 'http://localhost:8080'
        airflow_user = 'admin'
        airflow_password = 'admin'

        session = requests.Session()
        login_url = f"{airflow_url}/login/"

        # Step 1: Retrieve the login page to grab the CSRF token.
        login_page = session.get(login_url)
        if login_page.status_code != 200:
            return Response(
                {"error": "Unable to load Airflow login page."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Extract CSRF token using regex.
        csrf_token_match = re.search(
            r'<input[^>]*name=[\'"]csrf_token[\'"][^>]*value=[\'"]([^\'"]+)[\'"]',
            login_page.text
        )
        csrf_token = csrf_token_match.group(1) if csrf_token_match else None
        if not csrf_token:
            csrf_token = session.cookies.get("csrf_token")

        # Prepare login payload and headers.
        payload = {
            "username": airflow_user,
            "password": airflow_password,
        }
        if csrf_token:
            payload["csrf_token"] = csrf_token
        headers = {"Referer": login_url}
        if csrf_token:
            headers["X-CSRFToken"] = csrf_token

        # Authenticate with Airflow.
        login_response = session.post(login_url, data=payload, headers=headers)
        if login_response.status_code != 200:
            return Response(
                {"error": "Airflow login failed.", "details": login_response.text},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Step 2: Retrieve the list of all DAGs.
        dags_url = f"{airflow_url}/api/v1/dags"
        dags_response = session.get(dags_url)
        if dags_response.status_code != 200:
            return Response(
                {"error": "Failed to fetch DAGs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        dags_data = dags_response.json()
        dags = dags_data.get("dags", [])

        all_dag_logs = {}

        # Step 3: For each DAG, fetch its DAG runs and logs.
        for dag in dags:
            dag_id = dag.get("dag_id")
            dag_runs_url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns"
            dag_runs_response = session.get(dag_runs_url)
            if dag_runs_response.status_code != 200:
                # Skip this DAG if we cannot fetch its runs.
                continue

            dag_runs_data = dag_runs_response.json()
            dag_runs = dag_runs_data.get("dag_runs", [])
            dag_logs = {}

            # Step 4: For each DAG run, fetch task instances and logs.
            for dag_run in dag_runs:
                run_id = dag_run.get("dag_run_id")
                task_instances_url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances"
                ti_response = session.get(task_instances_url)
                if ti_response.status_code != 200:
                    continue

                ti_data = ti_response.json()
                task_instances = ti_data.get("task_instances", [])
                run_logs = {}

                for task_instance in task_instances:
                    task_id = task_instance.get("task_id")
                    try_number = task_instance.get("try_number", 1)
                    log_url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}"
                    log_response = session.get(log_url)
                    if log_response.status_code == 200:
                        run_logs[task_id] = log_response.text
                    else:
                        run_logs[task_id] = f"Error fetching log: {log_response.status_code}"
                dag_logs[run_id] = run_logs

            all_dag_logs[dag_id] = dag_logs

        return Response({"all_logs": all_dag_logs}, status=status.HTTP_200_OK)






class AirflowLogsViewNonSession(APIView):
    def get(self, request, *args, **kwargs):
        # Airflow configuration (these could also be stored in settings)
        airflow_url = 'http://localhost:8080'
        airflow_user = 'admin'
        airflow_password = 'admin'
        auth = (airflow_user, airflow_password)

        # Step 1: Retrieve the list of all DAGs.
        dags_url = f"{airflow_url}/api/v1/dags"
        dags_response = requests.get(dags_url, auth=auth)
        if dags_response.status_code != 200:
            return Response(
                {"error": "Failed to fetch DAGs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        dags_data = dags_response.json()
        dags = dags_data.get("dags", [])

        all_dag_logs = {}

        # Step 2: For each DAG, fetch its DAG runs and logs.
        for dag in dags:
            dag_id = dag.get("dag_id")
            dag_runs_url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns"
            dag_runs_response = requests.get(dag_runs_url, auth=auth)
            if dag_runs_response.status_code != 200:
                continue

            dag_runs_data = dag_runs_response.json()
            dag_runs = dag_runs_data.get("dag_runs", [])
            dag_logs = {}

            # Step 3: For each DAG run, fetch task instances and logs.
            for dag_run in dag_runs:
                run_id = dag_run.get("dag_run_id")
                task_instances_url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances"
                ti_response = requests.get(task_instances_url, auth=auth)
                if ti_response.status_code != 200:
                    continue

                ti_data = ti_response.json()
                task_instances = ti_data.get("task_instances", [])
                run_logs = {}

                for task_instance in task_instances:
                    task_id = task_instance.get("task_id")
                    try_number = task_instance.get("try_number", 1)
                    log_url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}"
                    log_response = requests.get(log_url, auth=auth)
                    if log_response.status_code == 200:
                        run_logs[task_id] = log_response.text
                    else:
                        run_logs[task_id] = f"Error fetching log: {log_response.status_code}"
                dag_logs[run_id] = run_logs

            all_dag_logs[dag_id] = dag_logs

        return Response({"all_logs": all_dag_logs}, status=status.HTTP_200_OK)
