"""
MongoDB Client for Appointment Storage.

Handles all database operations:
  - Connection management with graceful fallback
  - Appointment CRUD operations
  - Booking ID generation
"""

from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import config


class MongoDBClient:
    """Manages MongoDB connections and appointment operations."""

    def __init__(self, uri: str | None = None):
        self.uri = uri or config.MONGODB_URI
        self.db_name = config.MONGODB_DB_NAME
        self.collection_name = config.MONGODB_COLLECTION
        self.client = None
        self.db = None
        self.collection = None
        self.connected = False

        if self.uri:
            self._connect()

    def _connect(self):
        """Establish MongoDB connection."""
        try:
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            # Test the connection
            self.client.admin.command("ping")
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            self.connected = True
            print(f"[MongoDB] ✅ Connected to database: {self.db_name}")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"[MongoDB] ❌ Connection failed: {e}")
            self.connected = False
        except Exception as e:
            print(f"[MongoDB] ❌ Unexpected error: {e}")
            self.connected = False

    def save_appointment(self, context: dict) -> str | None:
        """
        Save an appointment to MongoDB.

        Args:
            context: The conversation context containing appointment details.

        Returns:
            Booking ID string if successful, None if failed.
        """
        if not self.connected:
            print("[MongoDB] ⚠️ Not connected — cannot save appointment")
            return None

        appointment = context.get("appointment", {})
        appointment_doc = {
            "patient_name": appointment.get("patient_name", ""),
            "contact_number": appointment.get("contact_number", ""),
            "preferred_date": appointment.get("preferred_date", ""),
            "preferred_time": appointment.get("preferred_time", ""),
            "department": context.get("department", "General Medicine"),
            "symptoms": context.get("symptoms", []),
            "severity": context.get("severity", "mild"),
            "status": "confirmed",
            "booking_timestamp": datetime.now(timezone.utc),
            "conversation_summary": self._build_summary(context),
        }

        try:
            result = self.collection.insert_one(appointment_doc)
            booking_id = str(result.inserted_id)
            print(f"[MongoDB] ✅ Appointment saved — ID: {booking_id}")
            return booking_id
        except Exception as e:
            print(f"[MongoDB] ❌ Failed to save appointment: {e}")
            return None

    def get_appointment(self, booking_id: str) -> dict | None:
        """Retrieve an appointment by its booking ID."""
        if not self.connected:
            return None
        try:
            from bson import ObjectId
            result = self.collection.find_one({"_id": ObjectId(booking_id)})
            if result:
                result["_id"] = str(result["_id"])
            return result
        except Exception as e:
            print(f"[MongoDB] ❌ Failed to retrieve appointment: {e}")
            return None

    def get_all_appointments(self) -> list[dict]:
        """Retrieve all appointments (for admin/debug)."""
        if not self.connected:
            return []
        try:
            results = list(self.collection.find().sort("booking_timestamp", -1).limit(50))
            for r in results:
                r["_id"] = str(r["_id"])
            return results
        except Exception as e:
            print(f"[MongoDB] ❌ Failed to retrieve appointments: {e}")
            return []

    def _build_summary(self, context: dict) -> str:
        """Build a brief conversation summary for the appointment record."""
        symptoms = ", ".join(context.get("symptoms", []))
        severity = context.get("severity", "unknown")
        department = context.get("department", "unknown")
        return (
            f"Patient reported: {symptoms}. "
            f"Assessed severity: {severity}. "
            f"Routed to: {department}."
        )

    def close(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            self.connected = False
            print("[MongoDB] Connection closed.")
