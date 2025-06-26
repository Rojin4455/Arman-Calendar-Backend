from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import GHLUser,Contact
from .serializers import GHLUserCalendarUpdateSerializer,GHLUserSerializer,ContactSerializer
from rest_framework.permissions import IsAdminUser, AllowAny

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import (
    AppointmentBookingSerializer,
    AppointmentUpdateSerializer,
    AppointmentResponseSerializer
)
from .services import GHLAppointmentService
from .models import GHLAppointment

from rest_framework import generics
from django.db.models import Q
from .pagination import StandardResultsSetPagination

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
        







class AppointmentBookingView(APIView):
    """API endpoint for booking appointments"""
    authentication_classes = []
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = AppointmentBookingSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            created_appointments, errors = GHLAppointmentService.book_appointments(
                serializer.validated_data
            )
            
            if not created_appointments and errors:
                return Response(
                    {'error': 'Failed to create any appointments', 'details': errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            response_data = {
                'message': f'Successfully created {len(created_appointments)} appointment(s)',
                'appointments': AppointmentResponseSerializer(created_appointments, many=True).data,
                'errors': errors
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AppointmentUpdateView(APIView):
    """API endpoint for updating appointments"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def put(self, request, appointment_id):
        # Pass appointment_id to serializer context for timezone handling
        serializer = AppointmentUpdateSerializer(
            data=request.data,
            context={'appointment_id': appointment_id}
        )
        
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            updated_appointment = GHLAppointmentService.update_appointment(
                appointment_id,
                serializer.validated_data
            )
            
            return Response(
                {
                    'message': 'Appointment updated successfully',
                    'appointment': AppointmentResponseSerializer(updated_appointment).data
                },
                status=status.HTTP_200_OK
            )
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def patch(self, request, appointment_id):
        """Partial update using PATCH"""
        return self.put(request, appointment_id)


class AppointmentDeleteView(APIView):
    """API endpoint for deleting appointments"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, appointment_id):
        try:
            GHLAppointmentService.delete_appointment(appointment_id)
            
            return Response(
                {'message': 'Appointment deleted successfully'},
                status=status.HTTP_200_OK
            )
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AppointmentListView(APIView):
    """API endpoint for listing appointments"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        appointments = GHLAppointment.objects.all().order_by('-created_at')
        
        # Optional filtering
        location_id = request.query_params.get('location_id')
        contact_id = request.query_params.get('contact_id')
        assigned_to = request.query_params.get('assigned_to')
        
        if location_id:
            appointments = appointments.filter(location_id=location_id)
        if contact_id:
            appointments = appointments.filter(contact_id=contact_id)
        if assigned_to:
            appointments = appointments.filter(assigned_to=assigned_to)
        
        serializer = AppointmentResponseSerializer(appointments, many=True)
        
        return Response({
            'appointments': serializer.data,
            'count': appointments.count()
        }, status=status.HTTP_200_OK)


class AppointmentDetailView(APIView):
    """API endpoint for getting appointment details"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, appointment_id):
        try:
            appointment = GHLAppointment.objects.get(id=appointment_id)
            serializer = AppointmentResponseSerializer(appointment)
            
            return Response(
                {'appointment': serializer.data},
                status=status.HTTP_200_OK
            )
            
        except GHLAppointment.DoesNotExist:
            return Response(
                {'error': 'Appointment not found'},
                status=status.HTTP_404_NOT_FOUND
            )





class ContactSearchView(generics.ListAPIView):
    serializer_class = ContactSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [AllowAny]
    

    def get_queryset(self):
        search = self.request.query_params.get('search', '')
        return Contact.objects.filter(
            Q(contact_id__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )


class GHLUserSearchView(generics.ListAPIView):
    serializer_class = GHLUserSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [AllowAny]


    def get_queryset(self):
        search = self.request.query_params.get('search', '')
        return GHLUser.objects.filter(
            Q(user_id__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )