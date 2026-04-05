#!/usr/bin/env python3
"""
ERPNext SaaS Auto-Provisioning API v5.1
"""

import os
import json
import uuid
import re
import logging
import threading
import subprocess
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", str(uuid.uuid4()))

CONFIG = {
    "BENCH_PATH": os.getenv("BENCH_PATH", "/home/frappe/frappe-bench"),
    "BENCH_USER": os.getenv("BENCH_USER", "frappe"),
    "BENCH_BIN": "/home/frappe/.local/bin/bench",
    "BASE_DOMAIN": os.getenv("BASE_DOMAIN", "opentra.opentech.sa"),
    "MARIADB_ROOT_PASSWORD": os.getenv("MARIADB_ROOT_PASSWORD", "Admin_123"),
    "ADMIN_PASSWORD": os.getenv("DEFAULT_ADMIN_PASSWORD", "admin"),
    "API_KEY": os.getenv("API_KEY", "change-me"),
    "CERTBOT_EMAIL": os.getenv("CERTBOT_EMAIL", "admin@opentech.sa"),
    "APPS_TO_INSTALL": ["erpnext", "zatca_integration"],
    "LOG_DIR": os.getenv("LOG_DIR", "/home/frappe/frappe-bench/logs/provisioning"),
}

os.makedirs(CONFIG["LOG_DIR"], exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{CONFIG['LOG_DIR']}/provisioning.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("provisioning")

jobs = {}


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != CONFIG["API_KEY"]:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def get_bench_env():
    env = os.environ.copy()
    env["GIT_PYTHON_REFRESH"] = "quiet"
    env["HOME"] = f"/home/{CONFIG['BENCH_USER']}"
    env["PATH"] = (
        f"/home/{CONFIG['BENCH_USER']}/.local/bin:"
        "/usr/local/sbin:/usr/local/bin:"
        "/usr/sbin:/usr/bin:/sbin:/bin"
    )
    return env


def run_bench_command(cmd, site=None, timeout=600):
    bp = CONFIG["BENCH_PATH"]
    bb = CONFIG["BENCH_BIN"]
    if site:
        full_cmd = f"cd {bp} && {bb} --site {site} {cmd}"
    else:
        full_cmd = f"cd {bp} && {bb} {cmd}"
    logger.info(f"Running: {full_cmd}")
    try:
        result = subprocess.run(
            ["sudo", "-u", CONFIG["BENCH_USER"], "--", "bash", "-c", full_cmd],
            capture_output=True, text=True, timeout=timeout, env=get_bench_env(),
        )
        combined = result.stdout + "\n" + result.stderr
        if result.returncode == 0:
            return True, result.stdout, result.stderr
        for pattern in [r"Installing frappe", r"Updating DocTypes", r"already installed",
                        r"has been setup", r"Scheduler is disabled", r"Updating Dashboard"]:
            if re.search(pattern, combined):
                logger.info(f"Succeeded despite rc={result.returncode}")
                return True, result.stdout, result.stderr
        logger.error(f"Failed (rc={result.returncode}): {result.stderr[:500]}")
        return False, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def run_shell(cmd, timeout=300):
    logger.info(f"Shell: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def run_frappe_script(site_name, script_content):
    bp = CONFIG["BENCH_PATH"]
    bb = CONFIG["BENCH_BIN"]
    scripts_dir = f"{bp}/apps/frappe/frappe/utils"
    script_id = uuid.uuid4().hex[:8]
    module_name = f"_provision_{script_id}"
    script_path = f"{scripts_dir}/{module_name}.py"
    indented = "\n".join(
        "    " + line if line.strip() else ""
        for line in script_content.strip().split("\n")
    )
    wrapped_script = f"""import frappe

def run():
{indented}
"""
    try:
        with open(script_path, "w") as f:
            f.write(wrapped_script)
        subprocess.run(
            ["chown", f"{CONFIG['BENCH_USER']}:{CONFIG['BENCH_USER']}", script_path],
            capture_output=True,
        )
        cmd = f"cd {bp} && {bb} --site {site_name} execute frappe.utils.{module_name}.run"
        result = subprocess.run(
            ["sudo", "-u", CONFIG["BENCH_USER"], "--", "bash", "-c", cmd],
            capture_output=True, text=True, timeout=300, env=get_bench_env(),
        )
        logger.info(f"Script stdout: {result.stdout[:500]}")
        if result.returncode != 0:
            logger.warning(f"Script stderr: {result.stderr[:500]}")
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        logger.error(f"Script exception: {e}")
        return False, "", str(e)
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass
        try:
            import glob
            for f in glob.glob(f"{scripts_dir}/__pycache__/{module_name}*"):
                os.remove(f)
        except Exception:
            pass


def update_job(job_id, **kwargs):
    if job_id in jobs:
        jobs[job_id].update(kwargs)
        jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        logger.info(f"Job {job_id}: step={kwargs.get('step','?')} status={kwargs.get('status','?')}")


def validate_subdomain(subdomain):
    if not subdomain:
        return False, "Subdomain is required"
    if not re.match(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$', subdomain.lower()):
        return False, "Invalid subdomain."
    reserved = ["www", "mail", "ftp", "admin", "api", "ns1", "ns2"]
    if subdomain.lower() in reserved:
        return False, f"'{subdomain}' is reserved"
    return True, ""


# ===================================================================
#  FRAPPE SCRIPTS
# ===================================================================

SAUDI_DEFAULTS_SCRIPT = """
settings = {
    "country": "Saudi Arabia",
    "language": "ar",
    "date_format": "dd-mm-yyyy",
    "time_format": "HH:mm:ss",
    "number_format": "#,###.##",
    "currency": "SAR",
    "first_day_of_the_week": "Sunday",
}
for key, val in settings.items():
    try:
        frappe.db.set_single_value("System Settings", key, val)
    except Exception as e:
        print(f"Warning {key}: {e}")

if not frappe.db.exists("Currency", "SAR"):
    try:
        frappe.get_doc({
            "doctype": "Currency",
            "currency_name": "SAR",
            "name": "SAR",
            "symbol": "\\u0631.\\u0633",
            "fraction": "Halala",
            "fraction_units": 100,
            "number_format": "#,###.##",
            "smallest_currency_fraction_value": 0.01,
            "enabled": 1,
        }).insert(ignore_permissions=True)
    except Exception:
        pass

frappe.db.commit()
print("Phase 1 done: Saudi defaults applied")
"""

VAT_SETUP_SCRIPT = """
companies = frappe.get_all("Company", fields=["name", "abbr"])
if not companies:
    print("No companies found yet.")
    return

for co in companies:
    cn = co.name
    ab = co.abbr
    print(f"VAT setup for: {cn} ({ab})")

    pa = None
    for c in [f"Duties and Taxes - {ab}", f"Tax Assets - {ab}", f"Current Liabilities - {ab}"]:
        if frappe.db.exists("Account", c):
            pa = c
            break
    if not pa:
        for pattern in [f"%Duties and Taxes - {ab}", f"%Tax Assets - {ab}"]:
            result = frappe.db.get_value("Account", {"name": ["like", pattern], "company": cn, "is_group": 1}, "name")
            if result:
                pa = result
                break
    if not pa:
        pa = frappe.db.get_value("Account", {"company": cn, "is_group": 1, "root_type": "Liability"}, "name")
    if not pa:
        print(f"  No parent account for {cn}, skipping")
        continue

    print(f"  Parent: {pa}")

    for an, r in [("VAT 15%", 15.0), ("VAT Zero-Rated", 0.0), ("VAT Exempted", 0.0)]:
        full_name = f"{an} - {ab}"
        if not frappe.db.exists("Account", full_name):
            try:
                frappe.get_doc({
                    "doctype": "Account",
                    "account_name": an,
                    "parent_account": pa,
                    "company": cn,
                    "account_type": "Tax",
                    "tax_rate": r,
                    "is_group": 0,
                }).insert(ignore_permissions=True)
                print(f"  + {an}")
            except Exception as e:
                print(f"  ! {an}: {e}")
        else:
            current_parent = frappe.db.get_value("Account", full_name, "parent_account")
            if current_parent != pa:
                frappe.db.set_value("Account", full_name, "parent_account", pa)
                print(f"  ~ {an} moved to {pa}")
            else:
                print(f"  = {an} exists")

    tmpl_list = [
        ("Sales Taxes and Charges Template", f"Saudi VAT 15% - {ab}", f"VAT 15% - {ab}", 15.0, 1),
        ("Sales Taxes and Charges Template", f"Saudi VAT Zero - {ab}", f"VAT Zero-Rated - {ab}", 0.0, 0),
        ("Sales Taxes and Charges Template", f"Saudi VAT Exempt - {ab}", f"VAT Exempted - {ab}", 0.0, 0),
        ("Purchase Taxes and Charges Template", f"Saudi VAT 15% Purch - {ab}", f"VAT 15% - {ab}", 15.0, 1),
    ]

    for dt, ti, hd, rt, df in tmpl_list:
        if not frappe.db.exists(dt, ti):
            try:
                tx = {"charge_type": "On Net Total", "account_head": hd, "description": ti, "rate": rt}
                if "Purchase" in dt:
                    tx["category"] = "Total"
                    tx["add_deduct_tax"] = "Add"
                frappe.get_doc({"doctype": dt, "title": ti, "company": cn, "is_default": df, "taxes": [tx]}).insert(ignore_permissions=True)
                print(f"  + {ti}")
            except Exception as e:
                print(f"  ! {ti}: {e}")
        else:
            print(f"  = {ti} exists")

    try:
        if frappe.db.exists("DocType", "ZATCA Setting"):
            z = frappe.get_single("ZATCA Setting")
            if not z.company:
                z.company = cn
                z.save(ignore_permissions=True)
                print(f"  + ZATCA -> {cn}")
    except Exception as e:
        print(f"  ! ZATCA: {e}")

    frappe.db.commit()

print("VAT setup complete!")
"""

DEMO_DATA_SCRIPT = """
# Step 1: Relax custom_country mandatory
cf = frappe.db.get_value("Custom Field", {"fieldname": "custom_country", "dt": "Customer"}, "name")
if cf:
    frappe.db.set_value("Custom Field", cf, "reqd", 0)
    frappe.db.commit()
    frappe.clear_cache()
    print("1. custom_country relaxed")
else:
    print("1. No custom_country field")

# Step 2: Get main company info
main_company = frappe.get_all("Company", fields=["name", "abbr", "default_currency", "country", "chart_of_accounts"], order_by="creation asc", limit=1)
if not main_company:
    print("2. No company found")
    return
mc = main_company[0]
print(f"2. Main company: {mc.name} ({mc.abbr})")

# Step 3: Remove existing Demo Company
demo_name = f"{mc.name} (Demo)"
demo_abbr = f"{mc.abbr}D"
if frappe.db.exists("Company", demo_name):
    try:
        for dt in ["Sales Taxes and Charges Template", "Purchase Taxes and Charges Template"]:
            for t in frappe.get_all(dt, filters={"company": demo_name}, pluck="name"):
                frappe.delete_doc(dt, t, force=True, ignore_permissions=True)
        frappe.delete_doc("Company", demo_name, force=True, ignore_permissions=True)
        frappe.db.commit()
        print(f"3. Deleted existing {demo_name}")
    except Exception as e:
        print(f"3. Could not delete {demo_name}: {e}")
else:
    print(f"3. No existing {demo_name}")

# Step 4a: Create Demo Company manually
try:
    new_company = frappe.new_doc("Company")
    new_company.company_name = demo_name
    new_company.abbr = demo_abbr
    new_company.enable_perpetual_inventory = 1
    new_company.default_currency = mc.default_currency
    new_company.country = mc.country
    new_company.chart_of_accounts_based_on = "Standard Template"
    new_company.chart_of_accounts = mc.chart_of_accounts
    new_company.insert(ignore_permissions=True)
    frappe.db.set_single_value("Global Defaults", "demo_company", new_company.name)
    frappe.db.set_default("company", new_company.name)
    try:
        from erpnext.setup.setup_wizard.operations.install_fixtures import create_bank_account
        bank = create_bank_account({"company_name": new_company.name}, demo=True)
        if bank:
            frappe.db.set_value("Company", new_company.name, "default_bank_account", bank.name)
    except Exception:
        pass
    frappe.db.commit()
    demo_company = new_company.name
    print(f"4a. Created: {demo_company} ({demo_abbr})")
except Exception as e:
    print(f"4a. Error: {e}")
    return

# Step 4b: Create VAT for Demo Company
pa = None
for pattern in [f"%Duties and Taxes - {demo_abbr}", f"%Tax Assets - {demo_abbr}"]:
    result = frappe.db.get_value("Account", {"name": ["like", pattern], "company": demo_company, "is_group": 1}, "name")
    if result:
        pa = result
        break
if not pa:
    pa = frappe.db.get_value("Account", {"company": demo_company, "is_group": 1, "root_type": "Liability"}, "name")

if pa:
    print(f"4b. Demo tax parent: {pa}")
    for an, r in [("VAT 15%", 15.0), ("VAT Zero-Rated", 0.0), ("VAT Exempted", 0.0)]:
        if not frappe.db.exists("Account", f"{an} - {demo_abbr}"):
            try:
                frappe.get_doc({"doctype": "Account", "account_name": an, "parent_account": pa, "company": demo_company, "account_type": "Tax", "tax_rate": r, "is_group": 0}).insert(ignore_permissions=True)
            except Exception:
                pass
    for dt, ti, hd, rt, df in [
        ("Sales Taxes and Charges Template", f"Saudi VAT 15% - {demo_abbr}", f"VAT 15% - {demo_abbr}", 15.0, 1),
        ("Sales Taxes and Charges Template", f"Saudi VAT Zero - {demo_abbr}", f"VAT Zero-Rated - {demo_abbr}", 0.0, 0),
        ("Sales Taxes and Charges Template", f"Saudi VAT Exempt - {demo_abbr}", f"VAT Exempted - {demo_abbr}", 0.0, 0),
        ("Purchase Taxes and Charges Template", f"Saudi VAT 15% Purch - {demo_abbr}", f"VAT 15% - {demo_abbr}", 15.0, 1),
    ]:
        if not frappe.db.exists(dt, ti):
            try:
                tx = {"charge_type": "On Net Total", "account_head": hd, "description": ti, "rate": rt}
                if "Purchase" in dt:
                    tx["category"] = "Total"
                    tx["add_deduct_tax"] = "Add"
                frappe.get_doc({"doctype": dt, "title": ti, "company": demo_company, "is_default": df, "taxes": [tx]}).insert(ignore_permissions=True)
            except Exception:
                pass
    frappe.db.commit()
    print("4c. Demo VAT done")
    # Step 4c2: Set Round Off Cost Center
    try:
        cc = frappe.db.get_value("Cost Center", {"company": demo_company, "is_group": 0}, "name")
        if cc:
            frappe.db.set_value("Company", demo_company, "round_off_cost_center", cc)
            frappe.db.set_value("Company", demo_company, "depreciation_cost_center", cc)
            frappe.db.commit()
            print(f"4c2. Cost center set: {cc}")
    except Exception as e:
        print(f"4c2. Cost center error: {e}")
else:
    print("4b. No parent account for demo")

# Step 4d: Process masters
try:
    from erpnext.setup.demo import process_masters
    process_masters()
    print("4d. Masters created")
except Exception as e:
    print(f"4d. Masters error: {e}")

# Step 4e: Fix customers country
cust = frappe.get_all("Customer", filters={"custom_country": ["in", ["", None]]}, pluck="name")
for c in cust:
    frappe.db.set_value("Customer", c, "custom_country", "Saudi Arabia")
frappe.db.commit()
print(f"4e. Fixed {len(cust)} customers")

# Step 4f: Transactions
try:
    from erpnext.setup.demo import make_transactions
    make_transactions(demo_company)
    frappe.cache.delete_keys("bootinfo")
    print("4f. Transactions done")
except Exception as e:
    print(f"4f. Transactions error: {e}")

# Step 5: Restore mandatory
if cf:
    frappe.db.set_value("Custom Field", cf, "reqd", 1)
    print("5. custom_country mandatory again")

frappe.db.commit()
print(f"Customers: {frappe.db.count('Customer')}")
print(f"Items: {frappe.db.count('Item')}")
print(f"Sales Orders: {frappe.db.count('Sales Order')}")
print(f"Sales Invoices: {frappe.db.count('Sales Invoice')}")
print("Demo setup done!")
"""


# ===================================================================
#  PROVISIONING PIPELINE
# ===================================================================

def provision_site(job_id, subdomain, admin_password, company_name=None, install_demo=False):
    site_name = f"{subdomain}.{CONFIG['BASE_DOMAIN']}"
    try:
        site_dir = Path(CONFIG["BENCH_PATH"]) / "sites" / site_name
        if site_dir.exists():
            logger.info(f"{site_name} exists, skipping creation")
            update_job(job_id, step="creating_site", status="running", message="Site exists, skipping...")
        else:
            update_job(job_id, step="creating_site", status="running", message=f"Creating {site_name}...")
            success, out, err = run_bench_command(
                f"new-site {site_name} --mariadb-root-password {CONFIG['MARIADB_ROOT_PASSWORD']} --admin-password {admin_password} --no-mariadb-socket", timeout=300)
            if not success and not site_dir.exists():
                update_job(job_id, status="failed", step="creating_site", error=f"Failed: {err[:300]}")
                return

        for app_name in CONFIG["APPS_TO_INSTALL"]:
            update_job(job_id, step=f"installing_{app_name}", status="running", message=f"Installing {app_name}...")
            success, out, err = run_bench_command(f"install-app {app_name}", site=site_name, timeout=300)
            if not success:
                if "already installed" in (out + err):
                    logger.info(f"{app_name} already installed")
                elif app_name == "zatca_integration":
                    logger.warning(f"ZATCA warning: {err[:200]}")
                else:
                    update_job(job_id, status="failed", step=f"installing_{app_name}", error=f"Failed: {err[:300]}")
                    return

        update_job(job_id, step="setup_nginx", status="running", message="Configuring Nginx...")
        run_bench_command("setup nginx --yes", timeout=120)
        run_shell("sudo systemctl reload nginx")

        update_job(job_id, step="setup_ssl", status="running", message="Obtaining SSL certificate...")
        run_shell(f"sudo certbot --nginx -d {site_name} --non-interactive --agree-tos --email {CONFIG['CERTBOT_EMAIL']} --redirect", timeout=120)

        update_job(job_id, step="post_setup", status="running", message="Applying Saudi defaults...")
        run_frappe_script(site_name, SAUDI_DEFAULTS_SCRIPT)

        update_job(job_id, step="enable_scheduler", status="running", message="Enabling scheduler...")
        run_bench_command("enable-scheduler", site=site_name)
        run_bench_command("clear-cache", site=site_name)

        update_job(job_id, step="completed", status="completed",
                   message="Site provisioned successfully!",
                   site_url=f"https://{site_name}", site_name=site_name, install_demo=install_demo)
        logger.info(f"Site {site_name} provisioned successfully!")

    except Exception as e:
        logger.exception(f"Provisioning failed for {site_name}")
        update_job(job_id, status="failed", error=str(e))


# ===================================================================
#  API ENDPOINTS
# ===================================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "ERPNext SaaS Provisioning API",
        "version": "5.1",
        "timestamp": datetime.utcnow().isoformat(),
        "base_domain": CONFIG["BASE_DOMAIN"],
    })


@app.route("/api/provision", methods=["POST"])
@require_api_key
def provision():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    subdomain = data.get("subdomain", "").strip().lower()
    admin_password = data.get("admin_password", CONFIG["ADMIN_PASSWORD"])
    install_demo = data.get("install_demo", False)
    valid, msg = validate_subdomain(subdomain)
    if not valid:
        return jsonify({"error": msg}), 400
    site_name = f"{subdomain}.{CONFIG['BASE_DOMAIN']}"
    for jid, jdata in jobs.items():
        if jdata.get("site_name") == site_name and jdata.get("status") == "running":
            return jsonify({"error": "Provisioning in progress", "job_id": jid}), 409
    site_path = Path(CONFIG["BENCH_PATH"]) / "sites" / site_name
    if site_path.exists():
        if any(j.get("site_name") == site_name and j.get("status") == "completed" for j in jobs.values()):
            return jsonify({"error": f"{site_name} already provisioned", "site_url": f"https://{site_name}"}), 409
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id, "site_name": site_name, "subdomain": subdomain,
        "status": "queued", "step": "queued", "message": "Queued...",
        "install_demo": install_demo,
        "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat(),
    }
    thread = threading.Thread(
        target=provision_site,
        args=(job_id, subdomain, admin_password, data.get("company_name"), install_demo),
        daemon=True,
    )
    thread.start()
    return jsonify({
        "job_id": job_id, "site_name": site_name, "status": "queued",
        "install_demo": install_demo, "status_url": f"/api/site/status?job_id={job_id}",
    }), 202


@app.route("/api/site/status", methods=["GET"])
@require_api_key
def site_status():
    job_id = request.args.get("job_id")
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/sites", methods=["GET"])
@require_api_key
def list_sites():
    sites_path = Path(CONFIG["BENCH_PATH"]) / "sites"
    sites = []
    for item in sites_path.iterdir():
        if item.is_dir() and not item.name.startswith(".") and item.name != "assets":
            site_info = {"site_name": item.name, "url": f"https://{item.name}"}
            cp = item / "site_config.json"
            if cp.exists():
                try:
                    with open(cp) as f:
                        site_info["db_name"] = json.load(f).get("db_name")
                except Exception:
                    pass
            sites.append(site_info)
    return jsonify({"count": len(sites), "base_domain": CONFIG["BASE_DOMAIN"], "sites": sites})


@app.route("/api/site/delete", methods=["POST"])
@require_api_key
def delete_site():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    subdomain = data.get("subdomain", "").strip().lower()
    if not subdomain:
        return jsonify({"error": "subdomain required"}), 400
    site_name = f"{subdomain}.{CONFIG['BASE_DOMAIN']}"
    site_path = Path(CONFIG["BENCH_PATH"]) / "sites" / site_name
    if not site_path.exists():
        return jsonify({"error": f"{site_name} not found"}), 404
    success, out, err = run_bench_command(
        f"drop-site {site_name} --mariadb-root-password {CONFIG['MARIADB_ROOT_PASSWORD']} --force", timeout=120)
    if not success and site_path.exists():
        return jsonify({"error": f"Delete failed: {err[:300]}"}), 500
    run_bench_command("setup nginx --yes")
    run_shell("sudo systemctl reload nginx")
    return jsonify({"message": f"{site_name} deleted", "site_name": site_name})


@app.route("/api/site/run-vat-setup", methods=["POST"])
@require_api_key
def api_run_vat_setup():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    subdomain = data.get("subdomain", "").strip().lower()
    site_name = f"{subdomain}.{CONFIG['BASE_DOMAIN']}"
    if not (Path(CONFIG["BENCH_PATH"]) / "sites" / site_name).exists():
        return jsonify({"error": f"{site_name} not found"}), 404
    success, out, err = run_frappe_script(site_name, VAT_SETUP_SCRIPT)
    if success:
        return jsonify({"message": f"VAT setup done for {site_name}", "output": out})
    return jsonify({"error": f"VAT failed: {err[:300]}", "output": out}), 500


@app.route("/api/site/install-demo", methods=["POST"])
@require_api_key
def api_install_demo():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    subdomain = data.get("subdomain", "").strip().lower()
    site_name = f"{subdomain}.{CONFIG['BASE_DOMAIN']}"
    if not (Path(CONFIG["BENCH_PATH"]) / "sites" / site_name).exists():
        return jsonify({"error": f"{site_name} not found"}), 404
    success, out, err = run_frappe_script(site_name, DEMO_DATA_SCRIPT)
    if success:
        return jsonify({"message": f"Demo data installed for {site_name}", "output": out})
    return jsonify({"error": f"Demo failed: {err[:300]}", "output": out}), 500


@app.route("/api/site/setup-complete", methods=["POST"])
@require_api_key
def api_setup_complete():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    subdomain = data.get("subdomain", "").strip().lower()
    install_demo = data.get("install_demo", False)
    site_name = f"{subdomain}.{CONFIG['BASE_DOMAIN']}"
    if not (Path(CONFIG["BENCH_PATH"]) / "sites" / site_name).exists():
        return jsonify({"error": f"{site_name} not found"}), 404
    results = {}
    success, out, err = run_frappe_script(site_name, VAT_SETUP_SCRIPT)
    results["vat_setup"] = {"success": success, "output": out[:500] if out else ""}
    if install_demo:
        success, out, err = run_frappe_script(site_name, DEMO_DATA_SCRIPT)
        results["demo_data"] = {"success": success, "output": out[:500] if out else ""}
    return jsonify({"message": f"Post-wizard setup done for {site_name}", "results": results})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"Starting API v5.1 on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
