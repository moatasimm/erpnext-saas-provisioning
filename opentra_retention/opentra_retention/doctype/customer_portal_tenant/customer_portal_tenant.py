import frappe
from frappe.model.document import Document

class CustomerPortalTenant(Document):
    def validate(self):
        if not self.tenant_name:
            frappe.throw("Tenant Name is required")
        if not self.customer:
            frappe.throw("Customer is required")
