# Dated research batch for the shared tracker

Edit the same `lead-updates.json` file for each new discovery run. It contains only public employer facts and truthful fit/gap notes. A commit to `main` starts the guarded publisher. Never put the six-digit code, tokens, private migration goals, email bodies, personal PDFs or applicant contact details here.

Schema:

```json
{
  "batch_id": "2026-09-28-discovery-unique-id",
  "leads": [{
    "key": "employer.example|vacancy-id",
    "company": "Verified employer",
    "role": "Exact advertised title or clearly labelled speculative enquiry",
    "status": "READY_FOR_JEREMIE",
    "checked_at": "2026-09-28T03:00:00Z",
    "job_url": "https://employer.example/careers/exact-vacancy",
    "company_url": "https://employer.example/",
    "application_type": "ADVERTISED_VACANCY",
    "application_route": "SEEK",
    "fit": "Specific supported match, with the mandatory criteria checked",
    "gaps": ["Specific disclosed gap"],
    "attachments": []
  }],
  "status_updates": [{
    "key": "existing|vacancy-id",
    "status": "SKIPPED_EXPIRED",
    "checked_at": "2026-09-28T03:00:00Z",
    "status_evidence_url": "https://employer.example/careers/exact-vacancy",
    "status_check_note": "The employer's page states applications are closed."
  }]
}
```

The example is a schema illustration, not a real vacancy. Only commit actual verified records. For an EOI use `application_type: SPECULATIVE_EMPLOYMENT_ENQUIRY`, `vacancy_status: NO_ADVERTISED_VACANCY_VERIFIED` and `status: LEAD` or a truthful held state. No fabricated vacancy or hiring claim.

The publisher rejects batches checked more than 48 hours before processing, duplicate employer/role/URL records and divergent existing keys. It does not claim a successful website update until the action passes and the cloud read contains the new key. A failed run stays pending for guarded reconciliation. The automation must also check the private canonical journal and Gmail before any outreach; this public batch never authorizes an email.
