# AGENTS.md

给 AI 助手与维护者的入口。**改动本仓库前先读完这一页。**

## 这是什么

Misago —— 基于 Django 的论坛系统。本仓库是 fork,基线为上游 `516e6aeca`(v0.40.0),其上叠加了:中文支持、发帖页左右分栏编辑、Docker 国内镜像源、开发端口改为 5000。

- `misago/` —— 可安装的 Python 包。**54 个真实子目录**(另有 `__pycache__`),而 `INSTALLED_APPS` 共 60 项 = 46 个 `misago.*` + 14 个 Django/第三方;这 46 项里还包含 **`misago` 根包自身**,故只对应 45 个子目录。未安装的 9 个分三类:纯 Python 包 `collections/`、`healthcheck/`、`moderation/`、`test/`、`testutils/`;非 Python 目录 `locale/`、`static/`、`templates/`;以及**有 `apps.py` 却没被安装**的 `context_processors/`(见「已知问题」)。其中 `moderation/` 是个完整子系统却不是 app,别去找它的 `apps.py`。反向也有 4 个已安装但无 `apps.py`:`misago`(根)、`analytics`、`apiv2`、`plugins`
- `devproject/` —— 承载 `misago` 的开发期 Django project(`manage.py` 指向 `devproject.settings`)
- `frontend/` —— **论坛**前端(Webpack 5 + React 15 + Redux 3 + Bootstrap 3 + LESS + jQuery 2.2;htmx 的 npm 包名是 **`htmx.org`**,不是 `htmx`)
- `misago-admin/` —— **管理面板**前端(Vite 4 + React 18 + Apollo Client 3 + Bootstrap 4 + SCSS)
- `plugins/` —— 示例插件,由 `MISAGO_PLUGINS` 环境变量指向
- `dev-docs/` —— 开发者文档
- `scripts/` —— `check_docs_freshness.py`(文档漂移检查)与 `dev/`(一次性调试脚本)

## 环境约束

| 情况 | 说明 |
|---|---|
| Docker | `./dev` 的所有子命令都经 `docker compose`,**Docker Desktop 没启动就全部阻塞**。`docker compose ps` 应看到 5 个服务:postgres、redis、misago、celery-worker、mailpit |
| 本机 `python3` | 默认 **3.9**,低于项目要求的 3.12。直接跑项目脚本会因 `str \| None` 之类语法报 `TypeError` |
| 本机 Python 3.13 | `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`,未装项目依赖 |
| 无 Docker 时能做 | 文档生成与校验、`ruff` lint、纯静态/AST 检查、`scripts/check_docs_freshness.py`、`scripts/dev/check_layout.py` |
| 必须 Docker | `pytest`、`runserver`、`migrate`、任何 `import django` 的代码路径 |

**关键例外**:`generate_dev_docs.py` 只做 AST 解析 + 导入一个 dataclass 和一个 Enum,**用本机 Python 3.13 即可完整运行(含 `--check`),不需要 Django、数据库或 Docker**。文档工作永远不会被 Docker 阻塞。

## 验证命令

CI(`.github/workflows/tests.yml`)分两个 step。

**Linters** —— 提交前应本地全绿:

```bash
ruff check devproject misago plugins
ruff format devproject misago plugins --check
python generate_dev_docs.py --check
```

**Pytest** —— 需要数据库:

```bash
python manage.py makemigrations --check    # 迁移文件必须与 models 同步,漏了会红
pytest --run-slow --cov=misago
```

该 step 由 CI 注入 `DJANGO_SETTINGS_MODULE=devproject.test_settings`、`POSTGRES_DB/USER/PASSWORD=misago`、`POSTGRES_HOST=localhost`、`MISAGO_PLUGINS=plugins`。

本地跑测试:

```bash
./dev test                 # = docker compose run --rm misago pytest
./dev test --run-slow      # test 之后的参数原样透传给 pytest
```

**注意 `./dev test` 默认不带 `--run-slow` 也不带 `--cov`**,要与 CI 一致得自己加参数。

`.ruff.toml` 只启用 `select = ["I"]`(import 排序),`target-version = "py312"`。`pytest.ini` 用 `DJANGO_SETTINGS_MODULE = devproject.test_settings`,`testpaths = misago`。

前端:

```bash
cd frontend && npm run build      # 论坛前端 → misago/static/misago/{js,css}/
cd misago-admin && npm run build  # 管理面板 → misago/static/misago/admin/
```

## 六条硬约束(最容易踩的坑)

### 1. 模板绝大多数不与 app 同目录

`misago/templates/` 下共 **372** 个模板(371 个在 `misago/templates/misago/`,外加顶层的 `500.html`),而各 app 内只有 **52** 个。**找不到某 app 的模板时,先去 `misago/templates/misago/` 找**,不要以为它丢了。`misago/templates/tabler/` 是 SVG 图标集,不含 `.html`。

### 2. 前端构建产物是入库的

`misago/static/misago/js/{misago,vendor,hljs}.js`、`css/misago.css`、`admin/index.js` 都被 git 跟踪,这样 pip 安装后无需 npm 构建即可运行。

- **不要手改这些产物**,改 `frontend/src/` 或 `misago-admin/src/` 后重新构建
- 被 gitignore 的是 `devproject/static/`(collectstatic 输出),不是 `misago/static/`
- 两套前端用两套工具链、两个 Bootstrap 大版本,别混用

### 3. 有两套权限系统同时生效

同一个请求上**同时**挂着两个属性:

| 属性 | 来源 | 状态 |
|---|---|---|
| `request.user_permissions` | `misago/middleware/permissions.py:6` → `UserPermissionsProxy` | **新系统,写新代码用这个** |
| `request.user_acl` | `misago/acl/middleware.py:8` → `useracl.get_user_acl()` | 旧系统,但**远未退役** |

新代码一律用 `misago/permissions/`。不过遗留 ACL 的使用面比想象中大:排除 `misago/acl/` 自身与测试后,仍有 **28 个文件**引用 `user_acl` —— `users/` 22 个、`search/` 3 个,以及 `markup/flavours.py`(签名权限)、`categories/`、`settings.py` 各 1 个。**不要顺手删 `misago/acl/`。**

### 4. 有两个都叫 `settings` 的东西

| 写法 | 是什么 | 用量 |
|---|---|---|
| `from misago.conf import settings` | `StaticSettings`,代理 Django settings,取 `MISAGO_*` 常量 | 13 个文件 |
| `request.settings` | `DynamicSettings`(`SimpleLazyObject`),**值存在数据库里**,可在管理面板改 | 54 个文件 |

`request.settings.forum_name` 是 DB 值,`settings.MISAGO_POST_MENTIONS_LIMIT` 是 Django 值。搞混会读到完全不相干的东西。

两者都依赖 `request.cache_versions`(由 `misago/cache/middleware.py:8` 注入)做失效——这套机制同时被动态设置(`conf/dynamicsettings.py:8`)、`UserPermissionsProxy`(`permissions/proxy.py:18`)和 ACL 缓存(`acl/cache.py:7`)使用。

### 5. hook 文件的结构不能随意改

`generate_dev_docs.py` 用 AST 按固定形状解析每个 hook 文件,并在 CI 里跑 `--check`。每个 hook 文件必须是:

```python
class XHookAction(Protocol):     # docstring 描述被包装的 Misago 函数
    def __call__(self, ...) -> ...: ...

class XHookFilter(Protocol):     # docstring 描述插件要实现的函数
    def __call__(self, action, ...) -> ...: ...

class XHook(FilterHook[XHookAction, XHookFilter]):
    """描述 + `# Example` + ```python 代码块```"""
    __slots__ = FilterHook.__slots__   # 必须保留,不要删
    def __call__(self, action, ...): return super().__call__(action, ...)

x_hook = XHook()
```

`__slots__` 那行不能省:208 个 hook 单例全部常驻内存,`permissions/hooks/get_admin_category_permissions.py:72` 就此写着 `# important for memory usage!`。

偏离这个形状会让文档生成器出错或静默漏掉该 hook。另外生成器现在会校验:

- 每个 `misago/*/hooks/` 包都必须在 `generate_dev_docs.py` 的 `HOOKS_MODULES` 里
- 每个 `hooks/__init__.py` 必须有 `__all__`,且每个 hook 单例都必须在其中 re-export
- 每个 docstring 的代码围栏必须闭合,` ```python ` 块必须是**合法 Python**

改完 hook 记得跑 `python generate_dev_docs.py`(不带 `--check`)重新生成文档。

### 6. 有两套渲染引擎

| 模块 | 引擎 | 状态 |
|---|---|---|
| `misago/parser/` | markdown-it-py | **现行**,帖子内容走这条 |
| `misago/markup/` | Python-Markdown + html5lib | 半迁移的遗留 shim,仅剩 `legal/utils.py`、`threads/checksums.py`、`users/signatures.py` 三个消费者 |

注意 `misago/markup/api.py` 的 `preview_markup`(:35)已经改为委托给新 parser,而 `parse_markup`(:18)没有。

`parser` 是**两阶段**的:tokenize 时把引用/附件/@提及替换成占位符,存进 DB 的 `content_parsed` **不是最终 HTML**,渲染时才用 `replace_rich_text_tokens()`(`parser/richtext.py:18`)配合预取数据填充。

## 还有第三、第四套扩展机制

除了 hook,插件还能通过下列方式扩展。写插件前先确认该用哪一种:

| 机制 | 位置 | 说明 |
|---|---|---|
| `FilterHook` / `ActionHook` | `misago/*/hooks/` | 主力,208 个 hook 单例,分布在 18 个包 |
| `@extends` | `misago/plugins/extensions.py:38` | 动态合成 MRO 来扩展类,注册表是同文件 `:35` 的 `extensions` 单例 |
| `{% pluginoutlet %}` | `misago/plugins/enums.py` | 模板定点注入,`PluginOutlet` 枚举共 **47** 个位置 |
| `{% includecomponents %}` | `misago/context_processors/plugins.py` | 较新的模板注入,字典驱动,**7** 个区域:`before_head_close`、`after_body_open`、`before_body_close`、`above_navbar`、`below_navbar`、`above_footer`、`below_footer` |
| `misago/hooks.py` 的模块级列表 | 仓库根 | **遗留**,**7** 个 list:`apipatterns`、`context_processors`、`new_registrations_validators`、`post_search_filters`、`post_validators`、`markdown_extensions`、`parsing_result_processors`。无文档但仍在用 |

`base.html` 里 `pluginoutlet` 和 `includecomponents` 是并排使用的(`base.html:50-51`、`61-62`)。

## 文档地图

`dev-docs/index.md` 是总入口。

- `dev-docs/plugins/` —— 插件与 hook(**211 页 hook 参考是自动生成的,不要手改**)
- `dev-docs/parser/` —— 标记语言解析器与 AST
- `dev-docs/menus.md`、`notifications.md`、`html-attributes.md`、`template-components.md`
- `dev-docs/views-forms-templates-urls.md`、`translation-strings-contextual-markers.md` —— 风格指南

`dev-docs/plugins/hooks/` 下除 `index.md`、`action-hook.md`、`filter-hook.md` 外全部由生成器管理,每次运行会**删除**不在生成结果里的文件(`generate_dev_docs.py:345` 的 `write_files` 直接 `os.unlink`)。手写内容放这三个文件里。

### 源码锚点与漂移检查

手写文档在开头加 YAML frontmatter,声明它描述哪些源文件、以及最后一次核对是哪天:

```yaml
---
sources:
  - misago/permissions/proxy.py
  - misago/acl/buildacl.py
verified: 2026-09-26
---
```

然后:

```bash
python3 scripts/check_docs_freshness.py            # 报告,总是 exit 0
python3 scripts/check_docs_freshness.py --strict   # 有漂移则 exit 1,适合 CI
python3 scripts/check_docs_freshness.py --unanchored  # 额外列出未加锚点的文档
```

它把每个 `sources` 文件的最后提交日期与 `verified` 比对,列出已过期的页面,并报告指向不存在文件的坏引用。退出码含义:`0` 无漂移、`1` 有漂移(仅 `--strict`)、`2` **git 本身查询失败**——这是环境故障,脚本会明确报错而不是把每篇文档都误判成过期。

脚本只用标准库和 Python 3.9 语法,**不需要 Django、数据库或 Docker**,本机默认 `python3` 即可运行。

改动源文件后,若对应文档仍然准确,把它的 `verified` 更新为当天日期即可。

## 本 fork 的额外内容

| 路径 | 说明 |
|---|---|
| `scripts/dev/` | 一次性调试脚本,见其 README。不参与 CI |
| `scripts/check_docs_freshness.py` | 文档漂移检查,见上文「源码锚点」 |
| `translate_po.py` | 中文翻译辅助工具(630 行) |
| `migrate.sh` | `docker compose exec misago python manage.py migrate` 的包装 |
| `Dockerfile` | 改用 `mirrors.aliyun.com` apt/pip 源;**仅供本地开发**,生产用独立的 misago-docker |
| `docker-compose.yaml` | 宿主端口默认 **5000**(上游是 8000),可用 `MISAGO_DEVSERVER_PORT` 覆盖 |
| `misago/settings.py` | `LANGUAGES` 被裁到 `en-us` + `zh-hans`(`settings.py:263`),但 `misago/locale/` 仍有 122 个语言目录 |

## 已知问题

- `misago/threads/hooks/get_threads_users.py` 定义的 `get_threads_users_hook` **全库没有调用点**,是个死 hook
- `devproject/test_settings.py:54` 是 `TEST_NAME = "miasago_test"`(上游拼写错误)
- `frontend/webpack.config.js:70-77` 的 `.less` 规则写了两个 `use` 键,前一个(`style-loader`)是死代码,实际生效的是 `MiniCssExtractPlugin.loader`
- `misago/context_processors/apps.py` 声明了 `MisagoContextProcessorsConfig`,但该 app **不在** `INSTALLED_APPS`(60 项)里;它的函数是按点路径挂在 `TEMPLATE_CONTEXT_PROCESSORS` 上的
- `misago/users/tests/test_datadownloads.py` 有 3 个 `xfail`,原因写着 "post edits broken by `misago.posts` introduction"
- `requirements.in` 未区分运行时与开发依赖:`pytest*`、`ruff`、`django-debug-toolbar`、`freezegun`、`responses`、`coveralls` 都会随生产安装
- `docker-compose.yaml` 仍有已废弃的顶层 `version:` 键,每次 `docker compose` 都会告警
