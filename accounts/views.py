from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import GHLUser,Contact
from .serializers import GHLUserCalendarUpdateSerializer,GHLUserSerializer,ContactSerializer
from rest_framework.permissions import IsAdminUser, AllowAny

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import (
    AppointmentBookingSerializer,
    AppointmentUpdateSerializer,
    AppointmentResponseSerializer,
    RecurringAppointmentGroupSerializer,
    GHLAppointmentSerializer
)
from .services import GHLAppointmentService

from django.db.models import Q
from .pagination import StandardResultsSetPagination

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
from .models import RecurringAppointmentGroup, GHLAppointment
import logging
import requests

logger = logging.getLogger(__name__)

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
    # authentication_classes = []
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
    # authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    
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
    # authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    
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
    # authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    
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
    # authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    
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
    







class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class RecurringAppointmentGroupListView(generics.ListAPIView):
    """
    List all recurring appointment groups with pagination
    """
    queryset = RecurringAppointmentGroup.objects.filter(is_active=True)
    serializer_class = RecurringAppointmentGroupSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Optional filtering
        interval = self.request.query_params.get('interval')
        if interval:
            queryset = queryset.filter(interval=interval)
            
        location_id = self.request.query_params.get('location_id')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
            
        return queryset


class RecurringGroupAppointmentsView(generics.ListAPIView):
    """
    Retrieve all appointments under a specific recurring group
    """
    serializer_class = GHLAppointmentSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        group_id = self.kwargs['group_id']
        recurring_group = get_object_or_404(
            RecurringAppointmentGroup, 
            group_id=group_id,
            is_active=True
        )
        return GHLAppointment.objects.filter(
            recurring_group=recurring_group,
            is_active=True
        ).order_by('occurrence_number', 'start_time')


@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_recurring_group(request, group_id):
    """
    Delete a recurring group and all its appointments (bulk delete)
    """
    try:
        with transaction.atomic():
            # Get the recurring group
            recurring_group = get_object_or_404(
                RecurringAppointmentGroup,
                group_id=group_id,
                is_active=True
            )
            
            # Get all related appointments
            appointments = GHLAppointment.objects.filter(
                recurring_group=recurring_group,
                is_active=True
            )
            
            deleted_count = 0
            failed_deletions = []
            
            # Delete each appointment from GHL and local DB
            for appointment in appointments:
                try:
                    if appointment.ghl_appointment_id:
                        # Delete from GHL using your existing service
                        GHLAppointmentService.delete_appointment(appointment.id)
                        deleted_count += 1
                    else:
                        # If no GHL ID, just delete locally
                        appointment.delete()
                        deleted_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to delete appointment {appointment.id}: {str(e)}")
                    failed_deletions.append({
                        'appointment_id': appointment.id,
                        'error': str(e)
                    })
            
            # Mark the recurring group as inactive
            recurring_group.is_active = False
            recurring_group.save()
            
            response_data = {
                'message': 'Recurring group deleted successfully',
                'group_id': str(group_id),
                'deleted_appointments_count': deleted_count,
                'failed_deletions': failed_deletions
            }
            
            if failed_deletions:
                response_data['warning'] = 'Some appointments could not be deleted from GHL'
                return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
            
            return Response(response_data, status=status.HTTP_200_OK)
            
    except RecurringAppointmentGroup.DoesNotExist:
        return Response(
            {'error': 'Recurring group not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error deleting recurring group {group_id}: {str(e)}")
        return Response(
            {'error': f'Failed to delete recurring group: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_single_appointment(request, appointment_id):
    """
    Delete a single appointment from GHL and local database
    """
    try:
        # Use your existing service method
        result = GHLAppointmentService.delete_appointment(appointment_id)
        print("result: ", result)
        
        return Response(
            {
                'message': 'Appointment deleted successfully',
                'appointment_id': appointment_id
            },
            status=status.HTTP_200_OK
        )
        
    except ValueError as e:
        # Handle specific errors from your service
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return Response(
                {'error': error_msg},
                status=status.HTTP_404_NOT_FOUND
            )
        else:
            return Response(
                {'error': error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        logger.error(f"Unexpected error deleting appointment {appointment_id}: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


