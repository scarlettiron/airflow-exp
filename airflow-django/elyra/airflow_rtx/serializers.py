from rest_framework import serializers

class DagSerializer(serializers.Serializer):
    dag_id = serializers.CharField()
    description = serializers.CharField(allow_null=True, required=False)
    schedule_interval = serializers.CharField(allow_null=True, required=False)
    is_paused = serializers.BooleanField()
    tags = serializers.ListField(child=serializers.DictField(), required=False)


class DagListSerializer(serializers.Serializer):
    dags = DagSerializer(many=True)
    total_entries = serializers.IntegerField()