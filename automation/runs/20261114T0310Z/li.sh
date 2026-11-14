#!/bin/bash
# usage: li.sh TPR kw...
tpr=$1; shift
for k in "$@"; do for s in 0 25; do curl -s -A "Mozilla/5.0" "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$k")&location=Australia&f_TPR=$tpr&start=$s" | python3 -c "
import sys,re,html
t=sys.stdin.read()
for m in re.finditer(r'<li>.*?</li>',t,re.S):
  b=m.group(0)
  u=re.search(r'href=\"(https://au.linkedin.com/jobs/view/[^\"?]+)',b); ti=re.search(r'base-search-card__title\">\s*(.*?)\s*<',b,re.S); c=re.search(r'hidden-nested-link[^>]*>\s*(.*?)\s*<',b,re.S); l=re.search(r'job-search-card__location\">\s*(.*?)\s*<',b,re.S); d=re.search(r'datetime=\"(.*?)\"',b)
  if u and ti: print('\t'.join([html.unescape(ti.group(1)),html.unescape(c.group(1) if c else ''),l.group(1) if l else '',d.group(1) if d else '',u.group(1)]))
"; done; done
