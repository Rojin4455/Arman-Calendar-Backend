import requests
import time
from typing import List, Dict, Any, Optional
from django.utils.dateparse import parse_datetime
from django.db import transaction
from ghl_auth.models import GHLAuthCredentials
from django.utils.timezone import make_aware
from zoneinfo import ZoneInfo
import math
from datetime import datetime, timedelta
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY
from django.conf import settings
from .models import GHLAppointment, GHLUser, Contact, RecurringAppointmentGroup
import logging
from django.utils import timezone
import pytz

from dateutil.relativedelta import relativedelta

import json









def fetch_all_contacts(location_id: str, access_token: str = None) -> List[Dict[str, Any]]:
    """
    Fetch all contacts from GoHighLevel API with proper pagination handling.
    
    Args:
        location_id (str): The location ID for the subaccount
        access_token (str, optional): Bearer token for authentication
        
    Returns:
        List[Dict]: List of all contacts
    """

    
    
    
    
    base_url = "https://services.leadconnectorhq.com/contacts/"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    all_contacts = []
    start_after = None
    start_after_id = None
    page_count = 0
    
    while True:
        page_count += 1
        print(f"Fetching page {page_count}...")
        
        # Set up parameters for current request
        params = {
            "locationId": location_id,
            "limit": 100,  # Maximum allowed by API
        }
        
        # Add pagination parameters if available
        if start_after:
            params["startAfter"] = start_after
        if start_after_id:
            params["startAfterId"] = start_after_id
            
        try:
            response = requests.get(base_url, headers=headers, params=params)
            
            if response.status_code != 200:
                print(f"Error Response: {response.status_code}")
                print(f"Error Details: {response.text}")
                raise Exception(f"API Error: {response.status_code}, {response.text}")
            
            data = response.json()
            
            # Get contacts from response
            contacts = data.get("contacts", [])
            if not contacts:
                print("No more contacts found.")
                break
                
            all_contacts.extend(contacts)
            print(f"Retrieved {len(contacts)} contacts. Total so far: {len(all_contacts)}")
            
            # Check if there are more pages
            # GoHighLevel API uses cursor-based pagination
            meta = data.get("meta", {})
            
            # Update pagination cursors for next request
            if contacts:  # If we got contacts, prepare for next page
                last_contact = contacts[-1]
                
                # Get the ID for startAfterId (this should be a string)
                if "id" in last_contact:
                    start_after_id = last_contact["id"]
                
                # Get timestamp for startAfter (this must be a number/timestamp)
                start_after = None
                if "dateAdded" in last_contact:
                    # Convert to timestamp if it's a string
                    date_added = last_contact["dateAdded"]
                    if isinstance(date_added, str):
                        try:
                            from datetime import datetime
                            # Try parsing ISO format
                            dt = datetime.fromisoformat(date_added.replace('Z', '+00:00'))
                            start_after = int(dt.timestamp() * 1000)  # Convert to milliseconds
                        except:
                            # Try parsing as timestamp
                            try:
                                start_after = int(float(date_added))
                            except:
                                pass
                    elif isinstance(date_added, (int, float)):
                        start_after = int(date_added)
                        
                elif "createdAt" in last_contact:
                    created_at = last_contact["createdAt"]
                    if isinstance(created_at, str):
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            start_after = int(dt.timestamp() * 1000)
                        except:
                            try:
                                start_after = int(float(created_at))
                            except:
                                pass
                    elif isinstance(created_at, (int, float)):
                        start_after = int(created_at)
            
            # Check if we've reached the end
            total_count = meta.get("total", 0)
            if total_count > 0 and len(all_contacts) >= total_count:
                print(f"Retrieved all {total_count} contacts.")
                break
                
            # If we got fewer contacts than the limit, we're likely at the end
            if len(contacts) < 100:
                print("Retrieved fewer contacts than limit, likely at end.")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise
            
        # Add a small delay to be respectful to the API
        time.sleep(0.1)
        
        # Safety check to prevent infinite loops
        if page_count > 1000:  # Adjust based on expected contact count
            print("Warning: Stopped after 1000 pages to prevent infinite loop")
            break
    
    print(f"\nTotal contacts retrieved: {len(all_contacts)}")

    sync_contacts_to_db(all_contacts)
    # return all_contacts




def sync_contacts_to_db(contact_data):
    """
    Syncs contact data from API into the local Contact model using bulk upsert.
    
    Args:
        contact_data (list): List of contact dicts from GoHighLevel API
    """
    contacts_to_create = []
    existing_ids = set(Contact.objects.filter(contact_id__in=[c['id'] for c in contact_data]).values_list('contact_id', flat=True))

    for item in contact_data:
        date_added = parse_datetime(item.get("dateAdded")) if item.get("dateAdded") else None
        

        contact_obj = Contact(
            contact_id=item.get("id"),
            first_name=item.get("firstName"),
            last_name=item.get("lastName"),
            phone=item.get("phone"),
            email=item.get("email"),
            dnd=item.get("dnd", False),
            country=item.get("country"),
            date_added=date_added,
            tags=item.get("tags", []),
            custom_fields=item.get("customFields", []),
            location_id=item.get("locationId"),
            timestamp=date_added
        )

        if item.get("id") in existing_ids:
            # Update existing contact
            Contact.objects.filter(contact_id=item["id"]).update(
                first_name=contact_obj.first_name,
                last_name=contact_obj.last_name,
                phone=contact_obj.phone,
                email=contact_obj.email,
                dnd=contact_obj.dnd,
                country=contact_obj.country,
                date_added=contact_obj.date_added,
                tags=contact_obj.tags,
                custom_fields=contact_obj.custom_fields,
                location_id=contact_obj.location_id,
                timestamp=contact_obj.timestamp
            )
        else:
            contacts_to_create.append(contact_obj)

    if contacts_to_create:
        with transaction.atomic():
            Contact.objects.bulk_create(contacts_to_create, ignore_conflicts=True)

    print(f"{len(contacts_to_create)} new contacts created.")
    print(f"{len(existing_ids)} existing contacts updated.")









def pull_users(locationId):
    token = GHLAuthCredentials.objects.get(location_id=locationId)
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {token.access_token}',
        'Content-Type': 'application/json',
        'Version': '2021-07-28'  # or '2021-04-15' for calendars endpoint
    }

    calendars = []

    # Step 2: Fetch users and save/update GHLUser entries
    user_response = requests.get(
        f"https://services.leadconnectorhq.com/users/?locationId={locationId}",
        headers=headers
    )

    if user_response.status_code != 200:
        print(f"Error fetching users: {user_response.status_code} - {user_response.text}")
        return

    users_data = user_response.json().get("users", [])

    for user in users_data:
        user_id = user["id"]
        GHLUser.objects.update_or_create(
            user_id=user_id,
            defaults={
                "first_name": user.get("firstName", ""),
                "last_name": user.get("lastName", ""),
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "phone": user.get("phone", ""),
                "location_id": locationId,
                # "calendar_id": user_calendar_map.get(user_id)  # Map calendar if exists
            }
        )






logger = logging.getLogger('accounts.services')


class GHLAppointmentService:
    BASE_URL = "https://services.leadconnectorhq.com"
    
    @staticmethod
    def get_location_timezone(location_id):
        """Get timezone for a location from GHL credentials"""
        try:
            auth_creds = GHLAuthCredentials.objects.get(
                location_id=location_id,
                is_approved=True
            )
            tz_name = auth_creds.timezone or 'UTC'
            return pytz.timezone(tz_name)
        except (GHLAuthCredentials.DoesNotExist, pytz.exceptions.UnknownTimeZoneError):
            return pytz.UTC
    
    @staticmethod
    def convert_to_location_timezone(dt, location_id):
        """Convert datetime to location timezone"""
        if not dt:
            return dt
            
        location_tz = GHLAppointmentService.get_location_timezone(location_id)
        
        if timezone.is_naive(dt):
            # MODIFIED: If naive, assume it's already in the correct local time
            # Just make it timezone-aware without conversion
            return location_tz.localize(dt)
        else:
            # If aware, convert to location timezone
            return dt.astimezone(location_tz)
    
    @staticmethod
    def get_auth_credentials(location_id):
        """Get authentication credentials for a location"""
        try:
            return GHLAuthCredentials.objects.get(
                location_id=location_id,
                is_approved=True
            )
        except GHLAuthCredentials.DoesNotExist:
            raise ValueError(f"No valid credentials found for location {location_id}")
    
    # @staticmethod
    # def generate_rrule(interval, count, start_date):
    #     """Generate RRULE string for recurring appointments"""
    #     freq_map = {
    #         'daily': DAILY,
    #         'weekly': WEEKLY,
    #         'monthly': MONTHLY
    #     }
        
    #     if interval not in freq_map:
    #         raise ValueError(f"Invalid interval: {interval}")
        
    #     # Ensure start_date is timezone-aware
    #     if timezone.is_naive(start_date):
    #         start_date = timezone.make_aware(start_date)
        
    #     rule = rrule(
    #         freq=freq_map[interval],
    #         count=count,
    #         dtstart=start_date
    #     )
        
    #     return f"RRULE:FREQ={interval.upper()};INTERVAL=1;COUNT={count}"
    
    @staticmethod
    def create_ghl_appointment(appointment_data, access_token):
        """Create appointment in GHL via API"""
        url = f"{GHLAppointmentService.BASE_URL}/calendars/events/appointments"
        
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Version': '2021-04-15'
        }
        
        try:
            response = requests.post(url, json=appointment_data, headers=headers)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            try:
                error_detail = response.json()
            except:
                error_detail = response.text
            logger.error(f"GHL API Error: {e} | Detail: {error_detail}")
            logger.error(f"Payload: {json.dumps(appointment_data, indent=2)}")
            raise ValueError(f"GHL error: {error_detail}")
    
    @staticmethod
    def update_ghl_appointment(appointment_id, appointment_data, access_token):
        """Update appointment in GHL via API"""
        url = f"{GHLAppointmentService.BASE_URL}/calendars/events/appointments/{appointment_id}"
        
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Version': '2021-04-15'
        }
        
        try:
            response = requests.put(url, json=appointment_data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"GHL API Error: {e}")
            raise ValueError(f"Failed to update appointment in GHL: {str(e)}")
    
    @staticmethod
    def delete_ghl_appointment(appointment_id, access_token):
        """Delete appointment in GHL via API"""
        url = f"{GHLAppointmentService.BASE_URL}/calendars/events/{appointment_id}"
        
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}',
            'Version': '2021-04-15'
        }
        
        try:
            response = requests.delete(url, headers=headers)
            print("hereeee: deleted appointment: ", response)

            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"GHL API Error: {e}")
            raise ValueError(f"Failed to delete appointment in GHL: {str(e)}")
        

    @classmethod
    def calculate_occurrence_dates(cls, start_datetime, end_datetime, interval, every, count):
        """
        Calculate all occurrence dates for a recurring appointment
        
        Args:
            start_datetime: Initial start datetime
            end_datetime: Initial end datetime
            interval: 'daily', 'weekly', 'monthly', 'yearly'
            every: How often the appointment should repeat (e.g., every 2 weeks)
            count: Number of occurrences

        Returns:
            List of tuples (start_datetime, end_datetime) for each occurrence
        """
        if every < 1:
            raise ValueError("Parameter 'every' must be a positive integer greater than 0.")

        occurrences = []
        duration = end_datetime - start_datetime

        for i in range(count):
            if interval == 'daily':
                occurrence_start = start_datetime + timedelta(days=i * every)
            elif interval == 'weekly':
                occurrence_start = start_datetime + timedelta(weeks=i * every)
            elif interval == 'monthly':
                occurrence_start = start_datetime + relativedelta(months=i * every)
            elif interval == 'yearly':
                occurrence_start = start_datetime + relativedelta(years=i * every)
            else:
                raise ValueError(f"Unsupported interval: {interval}")

            occurrence_end = occurrence_start + duration
            occurrences.append((occurrence_start, occurrence_end))

        return occurrences
    
    @classmethod
    def book_appointments(cls, validated_data):
        from datetime import timezone as dt_timezone
        
        """Book single or recurring appointments"""
        created_appointments = []
        errors = []
        
        try:
            # Get auth credentials and timezone
            auth_creds = cls.get_auth_credentials(validated_data['locationId'])
            location_tz = cls.get_location_timezone(validated_data['locationId'])
            
            # Get contact details
            contact = Contact.objects.get(contact_id=validated_data['contactId'])
            
            # MODIFIED: Handle timezone conversion properly
            start_dt_local = validated_data['startDateTime']  # Already timezone-aware from validation
            end_dt_local = validated_data['endDateTime']      # Already timezone-aware from validation
            
            # Convert to UTC for GHL API (GHL expects UTC)
            start_dt_utc = start_dt_local.astimezone(pytz.UTC)
            end_dt_utc = end_dt_local.astimezone(pytz.UTC)
            
            # ... rest of the method remains the same
            
            recurring_group = None
            if validated_data['type'] == 'recurring':
                try:
                    recurring_group = RecurringAppointmentGroup.objects.create(
                        title=validated_data.get('title', 'Recurring Appointment'),
                        description=validated_data.get('description', ''),
                        interval=validated_data['interval'],
                        total_count=validated_data.get('count', 12),
                        original_start_time=start_dt_utc,
                        original_end_time=end_dt_utc,
                        contact_id=validated_data['contactId'],
                        location_id=validated_data['locationId']
                    )
                    logger.info(f"Created recurring group: {recurring_group.group_id}")
                except Exception as e:
                    logger.error(f"Failed to create recurring group: {str(e)}")
                    return [], [f"Failed to create recurring group: {str(e)}"]
            
            # Calculate occurrences
            if validated_data['type'] == 'recurring':
                occurrences = cls.calculate_occurrence_dates(
                    start_dt_utc,
                    end_dt_utc,
                    validated_data['interval'],
                    validated_data.get('every', 1),
                    validated_data.get('count', 12)
                )
            else:
                occurrences = [(start_dt_utc, end_dt_utc)]

            print("validated_data['userIds']:    ,", validated_data['userIds'])
            
            # Create appointments for each user and occurrence
            for user_id in validated_data['userIds']+[" "]:
                try:
                    recurring_calendar_id = ""
                    print("user id : ", user_id)
                    # Get user details
                    if user_id == " " and validated_data['type'] == "recurring":
                        recurring_calendar_id = "wF51PIbLM1nKPjraUEKv"
                    elif validated_data['type'] == "single" and user_id == " ":
                        recurring_calendar_id = "1rwE7cUSN5MxPeI1CHiB"
                    else:
                        user = GHLUser.objects.get(user_id=user_id)
                        
                        if not user.calendar_id:
                            errors.append(f"User {user_id} has no calendar assigned")
                            continue
                    
                    # Create appointments for each occurrence
                    for occurrence_number, (occurrence_start, occurrence_end) in enumerate(occurrences, 1):
                        try:
                            # MODIFIED: These are already in UTC, no need to convert again
                            occurrence_start_utc = occurrence_start
                            occurrence_end_utc = occurrence_end
                            
                            # Prepare appointment data for GHL
                            appointment_data = {
                                "title": validated_data.get('title', 'Appointment'),
                                "description": validated_data.get('description', ''),
                                "appointmentStatus": "confirmed",
                                "calendarId": recurring_calendar_id if recurring_calendar_id else user.calendar_id,
                                "locationId": validated_data['locationId'],
                                "contactId": validated_data['contactId'],
                                "startTime": occurrence_start_utc.isoformat(),
                                "endTime": occurrence_end_utc.isoformat(),
                                "ignoreFreeSlotValidation": True
                            }
                            
                            if not recurring_calendar_id:
                                appointment_data["assignedUserId"] = user_id
                            else:
                                appointment_data["assignedUserId"] = "qS7XxuUlhlrcyUUtmdGU"
                            
                            # Create appointment in GHL
                            ghl_response = cls.create_ghl_appointment(
                                appointment_data,
                                auth_creds.access_token
                            )
                            
                            # Save to local database (store in local timezone)
                            local_appointment = GHLAppointment.objects.create(
                                ghl_appointment_id=ghl_response.get('id'),
                                recurring_group=recurring_group,
                                occurrence_number=occurrence_number if recurring_group else None,
                                contact_id=validated_data['contactId'],
                                assigned_to=user_id,
                                calendar_id=user.calendar_id if not recurring_calendar_id else recurring_calendar_id,
                                location_id=validated_data['locationId'],
                                title=validated_data.get('title', 'Appointment'),
                                description=validated_data.get('description', ''),
                                start_time=start_dt_local,  # Store in local timezone
                                end_time=end_dt_local       # Store in local timezone
                            )
                            
                            created_appointments.append(local_appointment)
                            logger.info(f"Created appointment {local_appointment.id} for user {user_id}, occurrence {occurrence_number}")
                            
                        except Exception as e:
                            error_msg = f"Error creating occurrence {occurrence_number} for user {user_id}: {str(e)}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            continue
                    
                except GHLUser.DoesNotExist:
                    error_msg = f"User {user_id} not found"
                    logger.error(error_msg)
                    errors.append(error_msg)
                except Exception as e:
                    error_msg = f"Error processing user {user_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            return created_appointments, errors
            
        except Exception as e:
            logger.error(f"Failed to book appointments: {str(e)}")
            raise ValueError(f"Failed to book appointments: {str(e)}")

    
    @classmethod
    def update_appointment(cls, appointment_id, validated_data):
        """Update an existing appointment"""
        try:
            # Get local appointment
            appointment = GHLAppointment.objects.get(id=appointment_id)
            
            # Get auth credentials and timezone
            auth_creds = cls.get_auth_credentials(appointment.location_id)
            location_tz = cls.get_location_timezone(appointment.location_id)
            
            # Prepare update data
            update_data = {}
            if 'title' in validated_data:
                update_data['title'] = validated_data['title']
                appointment.title = validated_data['title']
            
            if 'description' in validated_data:
                update_data['description'] = validated_data['description']
                appointment.description = validated_data['description']
            
            if 'startDateTime' in validated_data:
                # MODIFIED: Assume incoming datetime is already in correct local time
                start_dt_local = validated_data['startDateTime']
                if timezone.is_naive(start_dt_local):
                    start_dt_local = location_tz.localize(start_dt_local)
                
                start_dt_utc = start_dt_local.astimezone(pytz.UTC)
                update_data['startTime'] = start_dt_utc.isoformat()
                appointment.start_time = start_dt_local
            
            if 'endDateTime' in validated_data:
                # MODIFIED: Assume incoming datetime is already in correct local time
                end_dt_local = validated_data['endDateTime']
                if timezone.is_naive(end_dt_local):
                    end_dt_local = location_tz.localize(end_dt_local)
                
                end_dt_utc = end_dt_local.astimezone(pytz.UTC)
                update_data['endTime'] = end_dt_utc.isoformat()
                appointment.end_time = end_dt_local
            
            # Update in GHL
            if appointment.ghl_appointment_id and update_data:
                cls.update_ghl_appointment(
                    appointment.ghl_appointment_id,
                    update_data,
                    auth_creds.access_token
                )
            
            # Save local changes
            appointment.save()
            
            return appointment
            
        except GHLAppointment.DoesNotExist:
            raise ValueError("Appointment not found")
        except Exception as e:
            logger.error(f"Failed to update appointment: {str(e)}")
            raise ValueError(f"Failed to update appointment: {str(e)}")

    
    @classmethod
    def delete_appointment(cls, appointment_id):
        """Delete an appointment"""
        try:
            # Get local appointment
            appointment = GHLAppointment.objects.get(id=appointment_id)
            print("hereeee: got 1")
            # Get auth credentials
            auth_creds = cls.get_auth_credentials(appointment.location_id)

            
            # Delete from GHL
            if appointment.ghl_appointment_id:
                print("hereeee: ")
                cls.delete_ghl_appointment(
                    appointment.ghl_appointment_id,
                    auth_creds.access_token
                )
            
            # Delete from local database
            appointment.delete()
            
            return True
            
        except GHLAppointment.DoesNotExist:
            raise ValueError("Appointment not found")
        except Exception as e:
            raise ValueError(f"Failed to delete appointment: {str(e)}")





