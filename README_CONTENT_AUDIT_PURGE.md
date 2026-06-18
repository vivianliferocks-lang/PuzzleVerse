# PuzzleVerse Local Content Audit + Purge Pack V1

Your image folder is about 1GB, so do not upload it here. Run these tools locally and upload only the small CSV/HTML reports or screenshots.

## Install requirements

```powershell
cd D:\Games\PuzzleVerse
python -m pip install -r tools\requirements_content_tools.txt
```

## Step 1: Audit everything locally

```powershell
python tools\content_audit_v2.py
```

Outputs:

```text
tools\content_audit_report.csv
tools\review_gallery_flagged.html
tools\review_gallery_all.html
tools\manual_overrides_template.csv
```

Open:

```text
D:\Games\PuzzleVerse\tools\review_gallery_flagged.html
```

This is the file you should review first.

## Step 2: Upload only the small report, not the 1GB image folder

Upload any of these to ChatGPT:

```text
tools\content_audit_report.csv
tools\manual_overrides_template.csv
screenshots from review_gallery_flagged.html
```

## Step 3: Quarantine very bad images safely

Dry run first:

```powershell
python tools\quarantine_from_audit_v2.py --min-severity 80
```

Actually move bad images to quarantine:

```powershell
python tools\quarantine_from_audit_v2.py --min-severity 80 --apply
```

This moves files into:

```text
assets\_quarantine_bad_images\
```

It does not delete permanently.

## Step 4: Manual replacements

Put replacement images somewhere like:

```text
replacement_images\
```

Fill this file:

```text
tools\manual_overrides_template.csv
```

Set:

```csv
decision, replacementPath
replace, replacement_images/gandhi_portrait.jpg
```

Then run:

```powershell
python tools\apply_manual_overrides_v2.py
```

## Step 5: Web re-curation from Wikimedia, optional

Use only for selected wrong levels first:

```powershell
python tools\recurate_wikimedia_v2.py --ids pv-108-mahatma-gandhi,pv-116-rani-lakshmibai --delay 8
```

If candidates look good, apply:

```powershell
python tools\recurate_wikimedia_v2.py --ids pv-108-mahatma-gandhi,pv-116-rani-lakshmibai --delay 8 --apply
```

For science missing images:

```powershell
python tools\recurate_wikimedia_v2.py --category science_discoveries --start 0 --limit 20 --delay 8
```

## Important

Do not run mass delete immediately. Always:
1. audit
2. review gallery
3. quarantine
4. replace
5. test game
6. commit
