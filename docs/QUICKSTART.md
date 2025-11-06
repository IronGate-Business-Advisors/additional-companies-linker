# Quick Start Guide

Get up and running in 5 minutes!

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your favorite editor
```

**Required settings in `.env`:**
```bash
MONGODB_CONNECTION_STRING=mongodb://your-mongo-host:27017
MONGODB_DATABASE=your_database
MONGODB_COLLECTION=submissions

PIPEDRIVE_API_KEY=your_api_key_here
PIPEDRIVE_DOMAIN=your-company.pipedrive.com

CONFIG_PROFILE=standard  # Use default profile
```

## 3. Test Connection

```bash
# Test with 5 submissions (dry-run, no changes made)
python -m src.main attach-products --dry-run --limit 5
```

**Expected output:**
```
✓ Connected to MongoDB (submissions: 1,234)
✓ Connected to Pipedrive
✓ Found 5 submissions to process

[1/5] Submission 507f1f77... (Deal #12345)
  Companies Processed: 2
  Total Value Added: $25.00
  ...
```

## 4. Process First 10 Submissions

```bash
python -m src.main attach-products --limit 10 --report test_report.csv
```

## 5. Verify in Pipedrive

1. Open one of the processed deals in Pipedrive
2. Check the "Products" tab
3. Verify additional companies appear as products
4. Verify quantities match W2 counts

## 6. Run Full Batch

Once confident, process all submissions:

```bash
python -m src.main attach-products --report full_run.csv
```

---

## Alternative: Interactive Menu

Use the convenience script for a guided experience:

```bash
chmod +x run.sh
./run.sh
```

**Menu options:**
- Test connection (5 submissions, dry-run)
- Preview batch (10 submissions, dry-run)  
- Process small batch (10 submissions)
- Process medium batch (50 submissions)
- Full run with report
- Custom command

---

## Common First-Time Issues

### "No submissions to process"

**Fix:** Check configuration:
```bash
# In .env, try:
PROCESS_COMPANIES=both  # Include primary companies
```

### "Orphaned: Deal not found"

**Fix:** Skip orphaned deals:
```bash
# In .env:
SKIP_ORPHANED_DEALS=true
```

### "Configuration error"

**Fix:** Verify all required fields in `.env`:
- MONGODB_CONNECTION_STRING
- MONGODB_DATABASE
- MONGODB_COLLECTION
- PIPEDRIVE_API_KEY
- PIPEDRIVE_DOMAIN

---

## What Happens?

```
MongoDB Submission → Extract Companies → Create Products in Pipedrive → Attach to Deal
```

**Example:**

```
Submission (Deal #12345):
  - Primary: "Acme Corp" (W2: 25)
  - Additional: "Acme Sub A" (W2: 10)
  - Additional: "Acme Sub B" (W2: 15)

          ↓ (script runs)

Pipedrive Deal #12345:
  + Product: "Acme Sub A" - $10
  + Product: "Acme Sub B" - $15
  = Deal Value: $25 (sum of products)
```

---

## Next Steps

- Read [README.md](README.md) for detailed configuration options
- Explore different [configuration profiles](README.md#configuration)
- Learn about [migration scenarios](README.md#migration--reconfiguration)
- Set up [scheduled runs](#automation-optional) (optional)

---

## Automation (Optional)

### Cron Job Example

Process new submissions daily:

```bash
# Add to crontab (crontab -e)
0 2 * * * cd /path/to/additional-companies-linker && python -m src.main attach-products --no-confirm --report daily_$(date +\%Y\%m\%d).csv >> logs/cron.log 2>&1
```

### Shell Script

```bash
#!/bin/bash
# run-daily.sh

cd /path/to/additional-companies-linker
source venv/bin/activate
python -m src.main attach-products \
    --no-confirm \
    --report "reports/daily_$(date +%Y%m%d).csv" \
    2>&1 | tee "logs/run_$(date +%Y%m%d).log"
```

---

## Getting Help

**Check logs:**
```bash
python -m src.main attach-products --verbose --limit 5
```

**Review reports:**
```bash
cat test_report.csv
```

**Validate configuration:**
```bash
python -m src.main attach-products --dry-run --limit 1
# Check configuration summary at start
```

---

## Success! 🎉

Your additional companies are now automatically linked as products in Pipedrive!

**What you've achieved:**
- ✅ Automated product creation from company data
- ✅ Accurate W2 count tracking
- ✅ Duplicate prevention
- ✅ Audit trail via CSV reports
- ✅ Safe, idempotent operations

For advanced usage, see the [full README](README.md).
