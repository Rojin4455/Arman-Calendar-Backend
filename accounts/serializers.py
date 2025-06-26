from rest_framework import serializers
from .models import GHLUser

class GHLUserCalendarUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GHLUser
        fields = ['calendar_id']