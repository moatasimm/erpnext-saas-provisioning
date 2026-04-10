# =====================================================================
# APP.PY PATCH — Add industry parameter support to /api/provision
# =====================================================================
#
# This file describes the 3 changes needed in app.py.
# Apply them manually to your existing app.py on GitHub.
#
# =====================================================================


# CHANGE 1: In the /api/provision endpoint, extract the industry parameter
# ---------------------------------------------------------------------
# Find this section (or similar):
#
#     data = request.get_json()
#     subdomain = data.get('subdomain')
#     admin_password = data.get('admin_password')
#     install_demo = data.get('install_demo', True)
#
# Add this line after admin_password:
#
#     industry = data.get('industry')  # Optional: Construction, Real Estate, etc.


# CHANGE 2: Pass industry into provision_site() function call
# ---------------------------------------------------------------------
# Find the call that starts the provisioning thread/job, e.g.:
#
#     thread = threading.Thread(
#         target=provision_site,
#         args=(job_id, subdomain, admin_password, install_demo)
#     )
#
# Add industry to the args tuple:
#
#     thread = threading.Thread(
#         target=provision_site,
#         args=(job_id, subdomain, admin_password, install_demo, industry)
#     )


# CHANGE 3: In provision_site() function, accept industry param and apply it
# ---------------------------------------------------------------------
# Update the function signature:
#
#     def provision_site(job_id, subdomain, admin_password, install_demo=True, industry=None):
#
# Then, after the bench commands that install ZATCA print format
# (around step "install_zatca_print_format"), add this new step:
#
#     if industry:
#         update_job(job_id, step="set_industry", status="running",
#                    message=f"Setting industry to {industry}...")
#         # Set industry on all companies on the site
#         set_industry_cmd = (
#             f'execute frappe.db.sql --kwargs '
#             f'"{{\\"query\\":\\"UPDATE \\\\`tabCompany\\\\` SET custom_industry_type=%s\\",'
#             f'\\"values\\":[\\"{industry}\\"]}}"'
#         )
#         run_bench_command(set_industry_cmd, site=site_name)
#         run_bench_command("clear-cache", site=site_name)


# =====================================================================
# USAGE AFTER PATCH
# =====================================================================
#
# POST /api/provision
# {
#   "subdomain": "construction1",
#   "admin_password": "Test@12345",
#   "install_demo": true,
#   "industry": "Construction"   <-- NEW
# }
#
# When industry="Construction" or "Real Estate":
#   - custom_industry_type field set on Company
#   - Setup Wizard hook will create Retention Payable account
#   - custom_enable_sales_retention will be enabled
#
# =====================================================================
