from django.urls import path
from . import views as v

urlpatterns = [
    path('get-dags', v.AirflowDagsView.as_view()),
    path('get-dag-logs/<str:dag_id>', v.AirflowDagLogsView.as_view()),
    path('get-all-dag-logs', v.AirflowAllDagLogsView.as_view()),
]
