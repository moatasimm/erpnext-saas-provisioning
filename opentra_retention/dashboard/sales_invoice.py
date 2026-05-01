# Dashboard configuration for Sales Invoice
# Adds a "Retention" section showing linked Retention Release documents.


def get_data(data=None):
    data = data or {}
    data["transactions"] = data.get("transactions", [])
    data["transactions"].append({
        "label": "Retention",
        "items": ["Retention Release"]
    })
    return data
