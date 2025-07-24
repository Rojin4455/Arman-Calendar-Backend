import requests

def get_location_name(location_id: str, access_token: str) -> str:
    url = f"https://services.leadconnectorhq.com/locations/{location_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise exception for HTTP errors

    data = response.json()
    return data.get("location", {}).get("name"),  data.get("location", {}).get("timezone")




import requests
from ghl_auth.models import GHLAuthCredentials
from accounts.models import Contact

def create_or_update_contact(data):
    try:
        contact_id = data.get("id")
        if not contact_id:
            print("❌ No contact ID provided in data:", data)
            return

        print("➡️ Attempting to create or update contact with ID:", contact_id)

        defaults = {
            "first_name": data.get("firstName"),
            "last_name": data.get("lastName"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "dnd": data.get("dnd", False),
            "country": data.get("country"),
            "date_added": data.get("dateAdded"),
            "location_id": data.get("locationId"),
        }

        print("📝 Defaults to be used:", defaults)

        contact, created = Contact.objects.update_or_create(
            contact_id=contact_id,
            defaults=defaults
        )

        action = "created" if created else "updated"
        print(f"✅ Contact {action}: {contact} (ID: {contact_id})")

    except Exception as e:
        print("❗ Error creating or updating contact:", str(e))
        import traceback
        traceback.print_exc()


def delete_contact(data):
    contact_id = data.get("id")
    try:
        contact = Contact.objects.get(contact_id=contact_id)
        contact.delete()
        print("Contact deleted:", contact_id)
    except Contact.DoesNotExist:
        print("Contact not found for deletion:", contact_id)