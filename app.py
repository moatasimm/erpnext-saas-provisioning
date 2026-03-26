#!/usr/bin/env python3
"""
ERPNext SaaS Auto-Provisioning API v3
======================================
Fixed: VAT setup uses bench execute instead of bench console
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


# ===================================================================
#  UTILITIES
# ===================================================================

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != CONFIG["API_KEY"]:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def get_bench_env():
    """Get environment variables for running bench commands."""
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
    """Run a bench command as frappe user."""
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
            capture_output=True,
            text=True,
            timeout=timeout,
            env=get_bench_env(),
        )

        combined = result.stdout + "\n" + result.stderr

        if result.returncode == 0:
            return True, result.stdout, result.stderr

        # bench often returns non-zero but operation succeeded
        success_patterns = [
            r"Installing frappe",
            r"Updating DocTypes",
            r"already installed",
            r"has been setup",
            r"Scheduler is disabled",
            r"Updating Dashboard",
        ]
        for pattern in success_patterns:
            if re.search(pattern, combined):
                logger.info(f"Succeeded despite rc={result.returncode} (matched: {pattern})")
                return True, result.stdout, result.stderr

        logger.error(f"Failed (rc={result.returncode}): {result.stderr[:500]}")
        return False, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout after {timeout}s")
        return False, "", "Command timed out"
    except Exception as e:
        logger.error(f"Exception: {e}")
        return False, "", str(e)


def run_shell(cmd, timeout=300):
    """Run a shell command directly."""
    logger.info(f"Shell: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        logger.error(f"Shell exception: {e}")
        return False, "", str(e)


def run_frappe_script(site_name, script_content):
    """
    Run a Python script inside Frappe context using bench execute.
    Creates a temporary module in frappe/utils/, runs it, then cleans up.
    This avoids the interactive bench console hanging issue.
    """
    bp = CONFIG["BENCH_PATH"]
    bb = CONFIG["BENCH_BIN"]

    # Create a proper Python module in frappe/utils/
    scripts_dir = f"{bp}/apps/frappe/frappe/utils"
    script_id = uuid.uuid4().hex[:8]
    module_name = f"_provision_{script_id}"
    script_path = f"{scripts_dir}/{module_name}.py"

    # Indent the script content to be inside a function
    indented = "\n".join(
        "    " + line if line.strip() else ""
        for line in script_content.strip().split("\n")
    )

    wrapped_script = f"""import frappe

def run():
{indented}
"""

    try:
        # Write script file
        with open(script_path, "w") as f:
            f.write(wrapped_script)

        # Make it owned by frappe
        subprocess.run(
            ["chown", f"{CONFIG['BENCH_USER']}:{CONFIG['BENCH_USER']}", script_path],
            capture_output=True
        )

        # Run via bench execute (non-interactive, no hanging!)
        cmd = f"cd {bp} && {bb} --site {site_name} execute frappe.utils.{module_name}.run"

        result = subprocess.run(
            ["sudo", "-u", CONFIG["BENCH_USER"], "--", "bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=120,
            env=get_bench_env(),
        )

        logger.info(f"Script stdout: {result.stdout[:500]}")
        if result.returncode != 0:
            logger.warning(f"Script stderr: {result.stderr[:500]}")

        return result.returncode == 0, result.stdout, result.stderr

    except Exception as e:
        logger.error(f"Script exception: {e}")
        return False, "", str(e)
    finally:
        # Cleanup script file
        try:
            os.remove(script_path)
        except OSError:
            pass
        # Cleanup .pyc cache
        try:
            import glob
            for f in glob.glob(f"{scripts_dir}/__pycache__/{module_name}*"):
                os.remove(f)
        except Exception:
            pass


def update_job(job_id, **kwargs):
    """Update job status in tracker."""
    if job_id in jobs:
        jobs[job_id].update(kwargs)
        jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        logger.info(
            f"Job {job_id}: "
            f"step={kwargs.get('step', '?')} "
            f"status={kwargs.get('status', '?')}"
        )


def validate_subdomain(subdomain):
    """Validate subdomain format."""
    if not subdomain:
        return False, "Subdomain is required"
    if not re.match(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$', subdomain.lower()):
        return False, "Invalid subdomain. Use lowercase letters, numbers, hyphens."
    reserved = ["www", "mail", "ftp", "admin", "api", "ns1", "ns2"]
    if subdomain.lower() in reserved:
        return False, f"'{subdomain}' is reserved"
    return True, ""


# ===================================================================
#  VAT SETUP SCRIPTS
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
                tx = {
                    "charge_type": "On Net Total",
                    "account_head": hd,
                    "description": ti,
                    "rate": rt,
                }
                if "Purchase" in dt:
                    tx["category"] = "Total"
                    tx["add_deduct_tax"] = "Add"
                frappe.get_doc({
                    "doctype": dt,
                    "title": ti,
                    "company": cn,
                    "is_default": df,
                    "taxes": [tx],
                }).insert(ignore_permissions=True)
                print(f"  + {ti}")
            except Exception as e:
                print(f"  ! {ti}: {e}")
        else:
            print(f"  = {ti} exists")

    try:
        if frappe.db.exists("DocType", "ZATCA Setting"):
            zatca = frappe.get_single("ZATCA Setting")
            if not zatca.company:
                zatca.company = cn
                zatca.save(ignore_permissions=True)
                print(f"  + ZATCA -> {cn}")
    except Exception as e:
        print(f"  ! ZATCA: {e}")

    frappe.db.commit()

print("VAT setup complete!")
"""


# ===================================================================
#  PROVISIONING PIPELINE
# ===================================================================

def provision_site(job_id, subdomain, admin_password, company_name=None):
    """Full provisioning pipeline (runs in background thread)."""
    site_name = f"{subdomain}.{CONFIG['BASE_DOMAIN']}"

    try:
        site_dir = Path(CONFIG["BENCH_PATH"]) / "sites" / site_name

        if site_dir.exists():
            logger.info(f"{site_name} exists, skipping creation")
            update_job(job_id, step="creating_site", status="running",
                       message="Site exists, skipping creation...")
        else:
            update_job(job_id, step="creating_site", status="running",
                       message=f"Creating site {site_name}...")
            success, out, err = run_bench_command(
                f"new-site {site_name} "
                f"--mariadb-root-password {CONFIG['MARIADB_ROOT_PASSWORD']} "
                f"--admin-password {admin_password} "
                f"--no-mariadb-socket",
                timeout=300)
            if not success and not site_dir.exists():
                update_job(job_id, status="failed", step="creating_site",
                           error=f"Failed: {err[:300]}")
                return

        for app_name in CONFIG["APPS_TO_INSTALL"]:
            update_job(job_id, step=f"installing_{app_name}", status="running",
                       message=f"Installing {app_name}...")
            success, out, err = run_bench_command(
                f"install-app {app_name}", site=site_name, timeout=300)
            if not success:
                if "already installed" in (out + err):
                    logger.info(f"{app_name} already installed")
                elif app_name == "zatca":
                    logger.warning(f"ZATCA warning: {err[:200]}")
                else:
                    update_job(job_id, status="failed",
                               step=f"installing_{app_name}",
                               error=f"Failed: {err[:300]}")
                    return

        update_job(job_id, step="setup_nginx", status="running",
                   message="Configuring Nginx...")
        run_bench_command("setup nginx --yes", timeout=120)
        run_shell("sudo systemctl reload nginx")

        update_job(job_id, step="setup_ssl", status="running",
                   message="Obtaining SSL certificate...")
        run_shell(
            f"sudo certbot --nginx -d {site_name} "
            f"--non-interactive --agree-tos "
            f"--email {CONFIG['CERTBOT_EMAIL']} "
            f"--redirect", timeout=120)

        update_job(job_id, step="post_setup", status="running",
                   message="Applying Saudi Arabia defaults...")
        run_frappe_script(site_name, SAUDI_DEFAULTS_SCRIPT)

        update_job(job_id, step="enable_scheduler", status="running",
                   message="Enabling scheduler...")
        run_bench_command("enable-scheduler", site=site_name)
        run_bench_command("clear-cache", site=site_name)

        update_job(job_id, step="completed", status="completed",
                   message="Site provisioned successfully!",
                   site_url=f"https://{site_name}",
                   site_name=site_name)
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
        "version": "3.0",
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

    valid, msg = validate_subdomain(subdomain)
    if not valid:
        return jsonify({"error": msg}), 400

    site_name = f"{subdomain}.{CONFIG['BASE_DOMAIN']}"

    for jid, jdata in jobs.items():
        if jdata.get("site_name") == site_name and jdata.get("status") == "running":
            return jsonify({"error": "Provisioning in progress", "job_id": jid}), 409

    site_path = Path(CONFIG["BENCH_PATH"]) / "sites" / site_name
    if site_path.exists():
        if any(j.get("site_name") == site_name and j.get("status") == "completed"
               for j in jobs.values()):
            return jsonify({
                "error": f"{site_name} already provisioned",
                "site_url": f"https://{site_name}",
            }), 409

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "site_name": site_name,
        "subdomain": subdomain,
        "status": "queued",
        "step": "queued",
        "message": "Provisioning queued...",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    thread = threading.Thread(
        target=provision_site,
        args=(job_id, subdomain, admin_password, data.get("company_name")),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "job_id": job_id,
        "site_name": site_name,
        "status": "queued",
        "status_url": f"/api/site/status?job_id={job_id}",
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
        f"drop-site {site_name} "
        f"--mariadb-root-password {CONFIG['MARIADB_ROOT_PASSWORD']} "
        f"--force", timeout=120)

    if not success and site_path.exists():
        return jsonify({"error": f"Delete failed: {err[:300]}"}), 500

    run_bench_command("setup nginx --yes")
    run_shell("sudo systemctl reload nginx")

    return jsonify({"message": f"{site_name} deleted", "site_name": site_name})


@app.route("/api/site/run-vat-setup", methods=["POST"])
@require_api_key
def api_run_vat_setup():
    """Run Phase 2 VAT setup after Setup Wizard."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    subdomain = data.get("subdomain", "").strip().lower()
    site_name = f"{subdomain}.{CONFIG['BASE_DOMAIN']}"
    site_path = Path(CONFIG["BENCH_PATH"]) / "sites" / site_name

    if not site_path.exists():
        return jsonify({"error": f"{site_name} not found"}), 404

    success, out, err = run_frappe_script(site_name, VAT_SETUP_SCRIPT)

    if success:
        return jsonify({"message": f"VAT setup done for {site_name}", "output": out})
    else:
        return jsonify({"error": f"VAT failed: {err[:300]}", "output": out}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"Starting API v3 on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
