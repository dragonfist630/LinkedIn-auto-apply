"""
Standalone script to collect LinkedIn job links that have verified UK Visa Sponsor status.
Clicks into each job detail page and checks extension's verification text.

Usage:
    python collect_visa_jobs.py

Output:
    - Prints job links to terminal
    - Saves to CSV: visa_sponsor_jobs.csv
"""

import os
import csv
import time
import traceback
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config.search import search_terms, search_location, switch_number, sort_by, salary, experience_level, job_type, on_site, companies, location, industry, job_function, job_titles, benefits, commitments, under_10_applicants, in_your_network, fair_chance_employer
from config.secrets import username, password
from config.settings import click_gap

from modules.open_chrome import driver, wait, actions
from modules.helpers import print_lg, buffer
from modules.clickers_and_finders import try_xp, text_input, wait_span_click, multi_sel_noWait, boolean_button_click, scroll_to_view

OUTPUT_CSV = "visa_sponsor_jobs.csv"

# Override filters for this script
DATE_POSTED = "Past 24 hours"
EASY_APPLY = False  # Don't filter by Easy Apply


def is_logged_in() -> bool:
    """Check if already logged into LinkedIn."""
    if "feed" in driver.current_url or "jobs" in driver.current_url:
        return True
    try:
        driver.find_element(By.XPATH, '//button[normalize-space(.)="Start a post"]')
        return True
    except:
        return False


def login():
    """Login to LinkedIn."""
    driver.get("https://www.linkedin.com/login")
    if is_logged_in():
        print_lg("Already logged in!")
        return

    try:
        wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Forgot password?")))
        try:
            driver.find_element(By.ID, "username").send_keys(username)
        except:
            print_lg("Couldn't find username field.")
        try:
            driver.find_element(By.ID, "password").send_keys(password)
        except:
            print_lg("Couldn't find password field.")
        driver.find_element(By.XPATH, '//button[@type="submit" and contains(text(), "Sign in")]').click()
    except Exception as e:
        print_lg(f"Login issue: {e}")

    # Wait for redirect
    try:
        WebDriverWait(driver, 30).until(
            lambda d: "feed" in d.current_url or "jobs" in d.current_url or "checkpoint" in d.current_url
        )
        if "checkpoint" in driver.current_url:
            print_lg("Security checkpoint detected. Please complete verification manually...")
            WebDriverWait(driver, 120).until(
                lambda d: "feed" in d.current_url or "jobs" in d.current_url
            )
        print_lg("Login successful!")
    except:
        print_lg("Login may have failed. Continuing anyway...")


def set_search_location():
    """Set the search location filter."""
    if search_location.strip():
        try:
            print_lg(f'Setting search location: "{search_location.strip()}"')
            loc_input = try_xp(driver, ".//input[@aria-label='City, state, or zip code'and not(@disabled)]", False)
            text_input(actions, loc_input, search_location, "Search Location")
        except Exception as e:
            print_lg(f"Failed to set search location: {e}")


def apply_filters():
    """Apply LinkedIn job search filters — Past 24 hours, NO Easy Apply filter."""
    set_search_location()
    try:
        recommended_wait = 1 if click_gap < 1 else 0

        wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space()="All filters"]'))).click()
        buffer(3)  # Wait for filter modal to fully render

        wait_span_click(driver, sort_by, 10)
        wait_span_click(driver, DATE_POSTED, 10)  # Past 24 hours
        buffer(recommended_wait)

        multi_sel_noWait(driver, experience_level)
        multi_sel_noWait(driver, companies, actions)
        if experience_level or companies:
            buffer(recommended_wait)

        multi_sel_noWait(driver, job_type)
        multi_sel_noWait(driver, on_site)
        if job_type or on_site:
            buffer(recommended_wait)

        # NO Easy Apply filter — we want ALL jobs
        # (removed: if easy_apply_only: boolean_button_click(...))

        multi_sel_noWait(driver, location)
        multi_sel_noWait(driver, industry)
        if location or industry:
            buffer(recommended_wait)

        multi_sel_noWait(driver, job_function)
        multi_sel_noWait(driver, job_titles)
        if job_function or job_titles:
            buffer(recommended_wait)

        if under_10_applicants:
            boolean_button_click(driver, actions, "Under 10 applicants")
        if in_your_network:
            boolean_button_click(driver, actions, "In your network")
        if fair_chance_employer:
            boolean_button_click(driver, actions, "Fair Chance Employer")

        wait_span_click(driver, salary)
        buffer(recommended_wait)

        multi_sel_noWait(driver, benefits)
        multi_sel_noWait(driver, commitments)
        if benefits or commitments:
            buffer(recommended_wait)

        show_results = driver.find_element(By.XPATH, '//button[contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "apply current filters to show")]')
        show_results.click()

    except Exception as e:
        print_lg(f"Filter error: {e}")


def get_page_info():
    """Get pagination element and current page number."""
    try:
        for cls in ["jobs-search-pagination__pages", "artdeco-pagination", "artdeco-pagination__pages"]:
            try:
                pagination = driver.find_element(By.CLASS_NAME, cls)
                scroll_to_view(driver, pagination)
                current_page = int(pagination.find_element(By.XPATH, "//button[contains(@class, 'active')]").text)
                return pagination, current_page
            except:
                continue
    except:
        pass
    return None, None


def check_visa_in_detail() -> bool:
    """
    After clicking into a job, check the detail view for visa sponsor verification.
    Extension injects text like:
      - "CompanyName did file UK Visa in last couple of years." (SPONSOR)
      - "CompanyName did NOT file UK visa in last couple of years." (NOT SPONSOR)
    Returns True only if company DID file UK visa.
    """
    buffer(2)  # Wait for extension to process detail view
    try:
        page_source = driver.page_source
        # Check for the positive confirmation
        if "did file UK Visa in last couple of years" in page_source:
            # Make sure it's not the "did NOT" version
            # The extension uses exact text: "did file UK Visa" for positive, "did NOT file UK visa" for negative
            if "did NOT file UK visa" not in page_source:
                return True
            # Both present — check which one is for the selected job
            # Look for the hb_resultP element in the detail panel
            try:
                result_elements = driver.find_elements(By.CSS_SELECTOR, 'p.hb_resultP')
                for elem in result_elements:
                    text = elem.text
                    if "did file UK Visa in last couple of years" in text and "did NOT" not in text:
                        return True
            except:
                pass
        return False
    except:
        return False


def collect_visa_jobs():
    """Main function: search jobs, click into each, verify visa sponsor in detail view."""
    collected_jobs = []
    seen_ids = set()

    for search_term in search_terms:
        driver.get(f"https://www.linkedin.com/jobs/search/?keywords={search_term}")
        print_lg(f'\n>>> Searching: "{search_term}" <<<\n')

        apply_filters()

        pages_scraped = 0
        max_pages = 10  # Safety limit

        while pages_scraped < max_pages:
            try:
                wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[@data-occludable-job-id]")))
            except:
                print_lg("No job listings found on this page.")
                break

            buffer(3)
            job_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")
            print_lg(f"Found {len(job_listings)} job listings on page.")

            for job in job_listings:
                try:
                    job_id = job.get_dom_attribute('data-occludable-job-id')
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    # Get title and company from list view
                    job_button = job.find_element(By.TAG_NAME, 'a')
                    scroll_to_view(driver, job_button, True)
                    title = job_button.text.split("\n")[0]

                    other_details = job.find_element(By.CLASS_NAME, 'artdeco-entity-lockup__subtitle').text
                    idx = other_details.find(' · ')
                    company = other_details[:idx] if idx > 0 else other_details
                    work_location = other_details[idx+3:] if idx > 0 else ""

                    # Click into job detail to trigger extension verification
                    try:
                        job_button.click()
                    except:
                        print_lg(f"  [CLICK FAIL] {title} | {company} — skipped")
                        continue

                    # Check detail view for visa sponsor text
                    is_visa_sponsor = check_visa_in_detail()

                    if is_visa_sponsor:
                        job_link = f"https://www.linkedin.com/jobs/view/{job_id}"
                        collected_jobs.append({
                            "job_id": job_id,
                            "title": title,
                            "company": company,
                            "location": work_location,
                            "link": job_link,
                            "search_term": search_term,
                            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        print_lg(f"  [VISA SPONSOR] {title} | {company} | {job_link}")
                    else:
                        print_lg(f"  [NO VISA] {title} | {company} — skipped")

                except Exception as e:
                    print_lg(f"Error processing job: {e}")
                    continue

            # Try next page
            pages_scraped += 1
            _, current_page = get_page_info()
            if current_page is None:
                break
            try:
                next_btn = driver.find_element(By.XPATH, f"//button[@aria-label='Page {current_page + 1}']")
                next_btn.click()
                buffer(3)
            except:
                print_lg("No more pages.")
                break

    return collected_jobs


def save_to_csv(jobs):
    """Save collected jobs to CSV."""
    if not jobs:
        print_lg("No visa sponsor jobs found.")
        return

    fieldnames = ["job_id", "title", "company", "location", "link", "search_term", "collected_at"]

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(jobs)

    print_lg(f"\nSaved {len(jobs)} jobs to {OUTPUT_CSV}")


GOV_SPONSOR_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "2026-05-05_-_Worker_and_Temporary_Worker.csv")


def load_gov_sponsors() -> set:
    """Load UK government sponsor register company names into a set (lowercased, stripped)."""
    sponsors = set()
    try:
        with open(GOV_SPONSOR_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Organisation Name", "").strip().strip('"').lower()
                if name:
                    sponsors.add(name)
        print_lg(f"Loaded {len(sponsors)} companies from UK gov sponsor register.")
    except FileNotFoundError:
        print_lg(f"WARNING: Gov sponsor CSV not found at {GOV_SPONSOR_CSV}")
    except Exception as e:
        print_lg(f"Error loading gov sponsor CSV: {e}")
    return sponsors


def validate_against_gov_register(jobs):
    """Cross-check collected jobs against UK government sponsor register CSV."""
    gov_sponsors = load_gov_sponsors()
    if not gov_sponsors:
        print_lg("Skipping validation — no gov sponsor data loaded.")
        return

    verified = []
    not_found = []

    for job in jobs:
        company = job["company"].strip().lower()
        # Try exact match first
        if company in gov_sponsors:
            verified.append(job)
            continue
        # Try partial match — check if company name is contained in any sponsor name or vice versa
        found = False
        for sponsor in gov_sponsors:
            if company in sponsor or sponsor in company:
                verified.append(job)
                found = True
                break
        if not found:
            not_found.append(job)

    print_lg(f"\n{'='*80}")
    print_lg(f"GOV REGISTER VALIDATION")
    print_lg(f"{'='*80}")
    print_lg(f"  Verified in gov register:     {len(verified)}/{len(jobs)}")
    print_lg(f"  NOT found in gov register:    {len(not_found)}/{len(jobs)}")

    if verified:
        print_lg(f"\n  --- VERIFIED (in gov register) ---")
        for i, job in enumerate(verified, 1):
            print_lg(f"  {i}. {job['title']} | {job['company']}")
            print_lg(f"     {job['link']}")

    if not_found:
        print_lg(f"\n  --- NOT IN GOV REGISTER ---")
        for i, job in enumerate(not_found, 1):
            print_lg(f"  {i}. {job['title']} | {job['company']}")
            print_lg(f"     {job['link']}")

    fieldnames = ["job_id", "title", "company", "location", "link", "search_term", "collected_at"]

    # Save verified jobs
    if verified:
        verified_csv = "visa_sponsor_jobs_verified.csv"
        with open(verified_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(verified)
        print_lg(f"\nSaved {len(verified)} gov-verified jobs to {verified_csv}")

    # Save not-found jobs
    if not_found:
        not_verified_csv = "not_visa_sponsor_jobs.csv"
        with open(not_verified_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(not_found)
        print_lg(f"Saved {len(not_found)} unverified jobs to {not_verified_csv}")


def main():
    try:
        # Login
        login()
        buffer(2)

        # Collect jobs
        jobs = collect_visa_jobs()

        # Print summary
        print_lg(f"\n{'='*80}")
        print_lg(f"RESULTS: Found {len(jobs)} verified UK Visa Sponsor jobs (Past 24 hours)")
        print_lg(f"{'='*80}\n")

        for i, job in enumerate(jobs, 1):
            print_lg(f"  {i}. {job['title']} | {job['company']}")
            print_lg(f"     {job['link']}\n")

        # Save to CSV
        save_to_csv(jobs)

        # Validate against UK government sponsor register
        validate_against_gov_register(jobs)

    except Exception as e:
        print_lg(f"Error: {e}")
        traceback.print_exc()
    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    main()
