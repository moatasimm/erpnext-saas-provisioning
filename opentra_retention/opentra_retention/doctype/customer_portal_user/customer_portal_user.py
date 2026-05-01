import frappe
from frappe.model.document import Document

class CustomerPortalUser(Document):
    def validate(self):
        # Ensure user is not already linked to another tenant
        existing = frappe.db.get_value(
            "Customer Portal User",
            {"user": self.user, "name": ["!=", self.name]},
            "name"
        )
        if existing:
            frappe.throw(
                f"User {self.user} is already linked to another tenant."
            )
