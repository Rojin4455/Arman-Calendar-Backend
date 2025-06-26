from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import GHLUser
from .serializers import GHLUserCalendarUpdateSerializer,GHLUserSerializer
from rest_framework.permissions import IsAdminUser, AllowAny



class UpdateUserCalendarView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, user_id):
        user = get_object_or_404(GHLUser, user_id=user_id)
        serializer = GHLUserCalendarUpdateSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            calendar_id = serializer.validated_data.get('calendar_id', '').strip()
            serializer.save(calendar_id=calendar_id if calendar_id else None)

            return Response({
                'success': True,
                'message': 'Calendar ID updated successfully',
                'calendar_id': user.calendar_id,
                'user_id': user.user_id
            })

        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class CalendarStatsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, location_id=None):
        try:
            users = GHLUser.objects.all()
            
            if location_id:
                users = users.filter(location_id=location_id)

            total = users.count()
            with_cal = users.exclude(calendar_id__isnull=True).exclude(calendar_id='').count()
            without_cal = total - with_cal
            serializer = GHLUserSerializer(users, many=True)

            return Response({
                'success': True,
                'stats': {
                    'total_users': total,
                    'users_with_calendar': with_cal,
                    'users_without_calendar': without_cal,
                    'calendar_coverage_percentage': round((with_cal / total * 100) if total > 0 else 0, 2),
                    "all_users":serializer.data
                }
            })

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)