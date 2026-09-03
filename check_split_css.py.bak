"""Render start-thread page + inject compiled split CSS + run layout assertions."""
import os, sys, json, re, django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'devproject.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
import lesscpy

# 1) 编译 posting-split.less
vars_block = '''
@screen-xs: 480px;
@screen-sm: 768px;
@screen-md: 992px;
@screen-lg: 1200px;
@screen-xs-min: @screen-xs;
@screen-sm-min: @screen-sm;
@screen-md-min: @screen-md;
@screen-lg-min: @screen-lg;
@screen-xs-max: (@screen-sm-min - 1);
@screen-sm-max: (@screen-md-min - 1);
@screen-md-max: (@screen-lg-min - 1);
@grid-gutter-width: 30px;
@navbar-height: 60px;
@line-height-computed: 20px;
@padding-base-vertical: 6px;
@padding-base-horizontal: 12px;
'''
with open('/app/frontend/src/style/misago/posting-split.less') as f:
    src = vars_block + f.read()
with open('/tmp/posting-split-test.less', 'w') as f:
    f.write(src)
split_css = lesscpy.compile('/tmp/posting-split-test.less')

# 2) 抓页面
U = get_user_model()
u = U.objects.filter(is_superuser=True).first() or U.objects.first()
c = Client()
c.force_login(u)
r = c.get('/c/first-category/3/start/')
html = r.content.decode()

# 3) 验证 DOM 标记
assert 'posting-split' in html, 'missing posting-split class'
assert 'posting-split-form' in html, 'missing posting-split-form class'
assert 'panel-message-preview' in html, 'missing preview panel'
assert 'misago-live-preview-body' in html, 'missing live preview body'
assert 'misago-live-preview-hide' in html, 'missing live preview hide marker'
assert 'PREVIEW_MARKUP_API' in html, 'missing PREVIEW_MARKUP_API in frontend context'
print('DOM checks: PASS')

# 4) 把编译出的 CSS 注入到 HTML 导出
injected = html.replace('</head>', '<style>\n' + split_css + '\n</style></head>', 1)
with open('/app/posting_split_preview.html', 'w', encoding='utf-8') as f:
    f.write(injected)
print('Injected HTML at /app/posting_split_preview.html')

# 5) 后端接口烟测
r2 = c.post('/api/preview-markup/', data=json.dumps({'post': '# hi\n\n**b** [quote]q[/quote]'}),
            content_type='application/json')
print('preview-markup status:', r2.status_code)
if r2.status_code == 200:
    d = r2.json()
    h = d.get('html', '')
    print('  h1     :', '<h1>' in h)
    print('  strong :', '<strong>' in h)
    print('  quote  :', 'rich-text-quote' in h)
else:
    print('  body:', r2.content[:200])
