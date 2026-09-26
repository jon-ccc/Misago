"""Extract compiled split CSS from the generated preview HTML."""
import re

with open('/app/posting_split_preview.html') as f:
    html = f.read()

# Find all <style> blocks and pick the one that contains posting-split
for m in re.finditer(r'<style>(.+?)</style>', html, re.S):
    body = m.group(1)
    if '.posting-split' in body:
        print(body)
        raise SystemExit(0)

print('NO MATCH')
raise SystemExit(1)
