from rest_framework import serializers


class MarkupSerializer(serializers.Serializer):
    post = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        return data


class PreviewMarkupSerializer(serializers.Serializer):
    post = serializers.CharField(required=False, allow_blank=True)
    attachments = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        max_length=100,
    )

    def validate(self, data):
        return data
