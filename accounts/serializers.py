from rest_framework import serializers
from datetime import datetime, timedelta
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY
from .models import GHLAppointment, Contact, GHLUser, RecurringAppointmentGroup
from ghl_auth.models import GHLAuthCredentials
from django.utils import timezone
import pytz
from rest_framework import serializers
from .models import Contact, GHLUser



class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = '__all__'

class GHLUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = GHLUser
        fields = '__all__'

class GHLUserCalendarUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GHLUser
        fields = ['calendar_id']


class GHLUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = GHLUser
        fields = "__all__"



class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = '__all__'

class GHLUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = GHLUser
        fields = '__all__'




class AppointmentBookingSerializer(serializers.Serializer):
    APPOINTMENT_TYPES = [
        ('single', 'Single'),
        ('recurring', 'Recurring'),
    ]
    
    INTERVAL_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    startDateTime = serializers.DateTimeField()
    endDateTime = serializers.DateTimeField()
    locationId = serializers.CharField(max_length=100)
    contactId = serializers.CharField(max_length=100)
    userIds = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1
    )
    type = serializers.ChoiceField(choices=APPOINTMENT_TYPES)
    title = serializers.CharField(max_length=200, default="Appointment")
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    # Recurring appointment fields
    interval = serializers.ChoiceField(
        choices=INTERVAL_CHOICES,
        required=False,
        allow_blank=True
    )
    count = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=365,
        default=12
    )
    every = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=365,
        default=1
    )
    # frequency = serializers.IntegerField(
    #     required=False,
    #     min_value=1,
    #     max_value=365,
    #     default=1
    # )
    
    def validate(self, attrs):
        # Get timezone from GHL credentials for proper datetime comparison
        try:
            auth_creds = GHLAuthCredentials.objects.get(
                location_id=attrs['locationId'],
                is_approved=True
            )
            # Get timezone, default to UTC if not set
            tz_name = auth_creds.timezone or 'UTC'
            location_tz = pytz.timezone(tz_name)
        except GHLAuthCredentials.DoesNotExist:
            # Fallback to UTC if no credentials found
            location_tz = pytz.UTC
        except pytz.exceptions.UnknownTimeZoneError:
            # Fallback to UTC for invalid timezone
            location_tz = pytz.UTC
        
        # Convert datetimes to timezone-aware if they aren't already
        start_dt = attrs['startDateTime']
        end_dt = attrs['endDateTime']
        
        # MODIFIED: If timezone-naive, assume they're already in the desired local time
        # and just make them timezone-aware without conversion
        if timezone.is_naive(start_dt):
            start_dt = location_tz.localize(start_dt)
            attrs['startDateTime'] = start_dt
        
        if timezone.is_naive(end_dt):
            end_dt = location_tz.localize(end_dt)
            attrs['endDateTime'] = end_dt
        
        # Get current time in the same timezone for comparison
        now = timezone.now().astimezone(location_tz)
        
        # Validate datetime order
        if start_dt >= end_dt:
            raise serializers.ValidationError("Start time must be before end time")
        
        # Validate past appointments (with some buffer for processing time)
        buffer_minutes = 5
        if start_dt < (now + timedelta(minutes=buffer_minutes)):
            raise serializers.ValidationError(
                f"Cannot book appointments in the past or within {buffer_minutes} minutes from now"
            )
        
        # Validate recurring appointment fields
        if attrs['type'] == 'recurring':
            if not attrs.get('interval'):
                raise serializers.ValidationError("Interval is required for recurring appointments")
        
        # Validate contact exists
        if not Contact.objects.filter(contact_id=attrs['contactId']).exists():
            raise serializers.ValidationError("Contact not found")
        
        # Validate users exist
        for user_id in attrs['userIds']:
            if not GHLUser.objects.filter(user_id=user_id).exists():
                raise serializers.ValidationError(f"User {user_id} not found")
        
        # Validate location has valid credentials
        if not GHLAuthCredentials.objects.filter(
            location_id=attrs['locationId'], 
            is_approved=True
        ).exists():
            raise serializers.ValidationError("No valid credentials found for this location")
        
        return attrs


class AppointmentUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    startDateTime = serializers.DateTimeField(required=False)
    endDateTime = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        # Get the appointment instance to get location timezone
        appointment_id = self.context.get('appointment_id')
        if appointment_id:
            try:
                appointment = GHLAppointment.objects.get(id=appointment_id)
                auth_creds = GHLAuthCredentials.objects.get(
                    location_id=appointment.location_id,
                    is_approved=True
                )
                tz_name = auth_creds.timezone or 'UTC'
                location_tz = pytz.timezone(tz_name)
            except (GHLAppointment.DoesNotExist, GHLAuthCredentials.DoesNotExist, pytz.exceptions.UnknownTimeZoneError):
                location_tz = pytz.UTC
        else:
            location_tz = pytz.UTC
        
        # Handle timezone for datetime fields
        if 'startDateTime' in attrs:
            if timezone.is_naive(attrs['startDateTime']):
                attrs['startDateTime'] = location_tz.localize(attrs['startDateTime'])
        
        if 'endDateTime' in attrs:
            if timezone.is_naive(attrs['endDateTime']):
                attrs['endDateTime'] = location_tz.localize(attrs['endDateTime'])
        
        # Validate datetime order
        if 'startDateTime' in attrs and 'endDateTime' in attrs:
            if attrs['startDateTime'] >= attrs['endDateTime']:
                raise serializers.ValidationError("Start time must be before end time")
        
        # Validate past appointments
        if 'startDateTime' in attrs:
            now = timezone.now().astimezone(location_tz)
            if attrs['startDateTime'] < (now + timedelta(minutes=5)):
                raise serializers.ValidationError("Cannot schedule appointments in the past or within 5 minutes from now")
        
        return attrs


class AppointmentResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = GHLAppointment
        fields = '__all__'



class RecurringAppointmentGroupSerializer(serializers.ModelSerializer):
    appointments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = RecurringAppointmentGroup
        fields = [
            'id', 'group_id', 'title', 'description', 'interval', 
            'total_count', 'original_start_time', 'original_end_time',
            'contact_id', 'location_id', 'created_at', 'updated_at',
            'is_active', 'appointments_count'
        ]
        read_only_fields = ['id', 'group_id', 'created_at', 'updated_at']
    
    def get_appointments_count(self, obj):
        return obj.appointments.filter(is_active=True).count()


class GHLAppointmentSerializer(serializers.ModelSerializer):
    recurring_group_title = serializers.CharField(
        source='recurring_group.title', 
        read_only=True
    )
    adjusted_start_time = serializers.SerializerMethodField()
    adjusted_end_time = serializers.SerializerMethodField()

    
    class Meta:
        model = GHLAppointment
        fields = [
            'id', 'ghl_appointment_id', 'contact_id', 'recurring_group',
            'occurrence_number', 'assigned_to', 'calendar_id', 'location_id',
            'title', 'description', 'start_time', 'end_time', 'status',
            'created_at', 'updated_at', 'is_active', 'recurring_group_title','adjusted_start_time','adjusted_end_time'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


    def get_adjusted_start_time(self, obj):
        if obj.start_time:
            # Subtract 5 hours.
            # Ensure the datetime is timezone-aware (obj.start_time should be if USE_TZ=True)
            # and then convert to the target timezone if necessary, or just subtract.
            # For displaying, it's often best to convert to a specific timezone.

            # Example 1: Simply subtract 5 hours (result will still be timezone-aware UTC-5 or naive)
            # This is the most direct translation of "make this time 5 hours before"
            adjusted_dt = obj.start_time - timedelta(hours=5)
            # Format as ISO 8601 string, or any other desired format
            return adjusted_dt.isoformat()

            # Example 2: Convert to a specific timezone (e.g., America/Chicago for CDT)
            # from pytz import timezone as pytz_timezone
            # cdt_timezone = pytz_timezone('America/Chicago')
            # adjusted_dt = obj.start_time.astimezone(cdt_timezone)
            # return adjusted_dt.isoformat() # Will include offset e.g., '2025-07-11T05:00:00-05:00'


        return None

    def get_adjusted_end_time(self, obj):
        if obj.end_time:
            # Apply the same logic as for start_time
            adjusted_dt = obj.end_time - timedelta(hours=5)
            return adjusted_dt.isoformat()
        return None


class AppointmentWithUserSerializer(serializers.ModelSerializer):
    assigned_user_name = serializers.SerializerMethodField()
    # Define custom fields for adjusted times
    adjusted_start_time = serializers.SerializerMethodField()
    adjusted_end_time = serializers.SerializerMethodField()
    print("hrerer12222")

    class Meta:
        model = GHLAppointment
        fields = [
            'id', 'ghl_appointment_id', 'contact_id', 'assigned_to', 'calendar_id',
            'location_id', 'title', 'description',
            # Include the original times if you still need them, or remove them
            'start_time', 'end_time',
            # Add the new adjusted time fields
            'adjusted_start_time', 'adjusted_end_time',
            'status', 'created_at', 'updated_at', 'is_active',
            'assigned_user_name'
        ]

    def get_assigned_user_name(self, obj):
        try:
            # Note: For production, consider caching GHLUser lookups
            # if this serializer is used frequently in a list.
            user = GHLUser.objects.get(user_id=obj.assigned_to)
            return user.name
        except GHLUser.DoesNotExist:
            # The 'date for service' string here seems a bit out of place for a user's name.
            # Consider if a better default or a null value might be appropriate if no user is found.
            return "N/A - User Not Found" # Or whatever makes sense contextually

    def get_adjusted_start_time(self, obj):
        if obj.start_time:
            # Subtract 5 hours.
            # Ensure the datetime is timezone-aware (obj.start_time should be if USE_TZ=True)
            # and then convert to the target timezone if necessary, or just subtract.
            # For displaying, it's often best to convert to a specific timezone.

            # Example 1: Simply subtract 5 hours (result will still be timezone-aware UTC-5 or naive)
            # This is the most direct translation of "make this time 5 hours before"
            adjusted_dt = obj.start_time - timedelta(hours=5)
            # Format as ISO 8601 string, or any other desired format
            return adjusted_dt.isoformat()

            # Example 2: Convert to a specific timezone (e.g., America/Chicago for CDT)
            # from pytz import timezone as pytz_timezone
            # cdt_timezone = pytz_timezone('America/Chicago')
            # adjusted_dt = obj.start_time.astimezone(cdt_timezone)
            # return adjusted_dt.isoformat() # Will include offset e.g., '2025-07-11T05:00:00-05:00'


        return None

    def get_adjusted_end_time(self, obj):
        if obj.end_time:
            # Apply the same logic as for start_time
            adjusted_dt = obj.end_time - timedelta(hours=5)
            return adjusted_dt.isoformat()
        return None