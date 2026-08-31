# Misago 技术文档

## 1. 项目概览

**Misago** 是一个现代化、功能完整的论坛系统，采用 Python 3.12 和 ES6 编写，后端基于 Django 5.2，前端使用 React.js。项目遵循 GPLv2 开源协议，当前版本为 **0.40.0**。

- **项目主页**: http://misago-project.org/
- **文档**: https://misago.gitbook.io/docs/
- **代码仓库**: https://github.com/rafalp/Misago/
- **作者**: Rafał Pitoń

---

## 2. 项目结构

```
Misago/
├── misago/                  # 核心 Python 包（Django 应用集合）
│   ├── __init__.py          # 版本号 0.40.0
│   ├── plugins/             # 插件系统
│   ├── conf/                # 配置系统
│   ├── core/                # 核心工具（中间件、分页、验证器等）
│   ├── acl/                 # 访问控制列表
│   ├── permissions/         # 权限系统
│   ├── admin/               # 管理面板
│   ├── users/               # 用户管理
│   ├── account/             # 用户账户设置
│   ├── profile/             # 用户资料页
│   ├── auth/                # 认证
│   ├── socialauth/          # 社交登录
│   ├── oauth2/              # OAuth2 客户端
│   ├── threads/             # 主题(Thread)和帖子(Post)
│   ├── categories/          # 分类
│   ├── posting/             # 发帖系统
│   ├── privatethreads/      # 私密主题
│   ├── threadevents/        # 主题事件
│   ├── postedits/           # 帖子编辑历史
│   ├── solutions/           # Q&A 采纳答案
│   ├── parser/              # 标记语言解析器
│   ├── markup/              # 标记语言风格
│   ├── polls/               # 投票系统
│   ├── likes/               # 点赞系统
│   ├── attachments/         # 附件管理
│   ├── notifications/       # 通知系统
│   ├── search/              # 搜索功能
│   ├── moderation/          # 内容审核
│   ├── apiv2/               # REST API v2
│   ├── graphql/             # GraphQL API
│   ├── themes/              # 主题系统
│   ├── menus/               # 菜单系统
│   ├── icons/               # 图标
│   ├── metatags/            # Meta 标签
│   ├── components/          # 模板组件
│   ├── context_processors/  # Django 上下文处理器
│   ├── htmx/                # HTMX 支持
│   ├── html/                # HTML 工具
│   ├── legal/               # 法律/GDPR 页面
│   ├── collections/         # 集合工具
│   ├── postgres/            # PostgreSQL 工具
│   ├── analytics/           # 分析
│   ├── healthcheck/         # 健康检查
│   ├── forumindex/          # 论坛首页
│   └── testutils/           # 测试工具
├── frontend/                # React.js 前端
├── dev-docs/                # 开发者文档
├── plugins/                 # 插件目录
├── dev                      # 开发环境脚本
├── Dockerfile               # Docker 构建文件
├── setup.py                 # Python 包安装配置
├── requirements.txt         # Python 依赖
├── requirements.in          # 原始依赖（pip-compile 源）
└── .ruff.toml               # Ruff 代码检查配置
```

---

## 3. 技术栈

### 3.1 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.12 | 运行语言 |
| Django | 5.2.15 | Web 框架 |
| Django REST Framework | 3.14.0 | REST API |
| Ariadne (GraphQL) | 0.22 | GraphQL API |
| Celery (Redis) | 5.3.6 | 异步任务队列 |
| PostgreSQL | - | 主数据库 |
| django-mptt | 0.16.0 | 树形分类结构 |
| markdown-it-py | 3.0.0 | Markdown 解析 |
| markdown | 3.5.2 | Markdown 渲染 |
| social-auth-app-django | - | 社交登录 |
| django-simple-sso | 1.2.0 | 单点登录 |
| Pillow | - | 图片处理 |
| Redis | - | 缓存/消息队列 |

### 3.2 前端

| 技术 | 用途 |
|------|------|
| React.js | 前端 UI 框架 |
| Webpack | 打包构建 |
| Bootstrap | CSS 框架 |
| HTMX | 动态 HTML 交互 |

### 3.3 开发工具

| 工具 | 用途 |
|------|------|
| Docker / Docker Compose | 容器化开发环境 |
| pytest | 测试框架 |
| Ruff | 代码检查 |
| Transifex | 国际化翻译管理 |

---

## 4. 核心架构

### 4.1 插件系统

插件系统是 Misago 最核心的扩展机制，由三个关键组件构成：

#### 4.1.1 插件发现 (`misago.plugins.discover`)

- `discover_plugins(plugins_path)` 扫描 `plugins/` 目录和 `pip-install.txt` 文件
- 自动将插件目录添加到 Python 路径
- 验证每个插件必须包含 `misago_plugin.py` 文件

#### 4.1.2 插件清单 (`misago.plugins.manifest`)

`MisagoPlugin` 是一个冻结的 dataclass，包含插件元数据：

```python
@dataclass(frozen=True)
class MisagoPlugin:
    name: Optional[str] = None          # 插件名称
    description: Optional[str] = None    # 描述
    license: Optional[str] = None        # 许可证
    icon: Optional[str] = None           # Font Awesome 图标
    color: Optional[str] = None          # 图标颜色
    version: Optional[str] = None        # 版本
    author: Optional[str] = None         # 作者
    homepage: Optional[str] = None       # 主页
    sponsor: Optional[str] = None        # 赞助链接
    help: Optional[str] = None           # 帮助链接
    bugs: Optional[str] = None           # Bug 追踪
    repo: Optional[str] = None           # 代码仓库
```

#### 4.1.3 扩展机制 (`misago.plugins.extensions`)

`ExtensionRegistry` 允许插件通过 `@extends` 装饰器扩展已有的类：

```python
from misago.plugins import extends

@extends(ThreadDetailView)
class ThreadLastPostLinkExtension:
    def get_header_meta(self, request, thread):
        data = super().get_header_meta(request, thread)
        # 扩展逻辑...
        return data
```

扩展通过 Python 多重继承动态组合，缓存在 `ExtensionRegistry` 中。

#### 4.1.4 插件数据模型 (`PluginDataModel`)

抽象基类，为模型添加 `plugin_data` JSON 字段（带 GIN 索引），供插件存储任意数据：

```python
class PluginDataModel(models.Model):
    plugin_data = models.JSONField(default=dict)
    class Meta:
        abstract = True
        indexes = [GinIndex(fields=["plugin_data"])]
```

### 4.2 Hook 系统

Hook 是插件注入自定义逻辑的预定义位置，分为两种类型：

#### 4.2.1 Action Hook (`ActionHook`)

"触发即忘"模式，按顺序调用所有注册的函数：

```python
class ActionHook(Generic[Action]):
    def append_action(self, action: Action)   # 追加到末尾
    def prepend_action(self, action: Action)  # 插入到开头
    def __call__(self, *args, **kwargs) -> List[Any]  # 执行所有 action
```

#### 4.2.2 Filter Hook (`FilterHook`)

过滤器链模式，包装标准函数，允许插件在函数执行前后或替代执行：

```python
class FilterHook(Generic[Action, Filter]):
    def append_filter(self, filter_: Filter)   # 追加（外层）
    def prepend_filter(self, filter_: Filter)  # 插入（内层，靠近原函数）
    def __call__(self, action, *args, **kwargs)  # 执行过滤链
```

Filter Hook 使用 `functools.reduce` 将过滤器函数链式组合，支持缓存优化。

### 4.3 权限系统

#### 4.3.1 UserPermissionsProxy

延迟加载的权限代理类，通过 `__getattr__` 和 `cached_property` 实现按需计算：

```python
class UserPermissionsProxy:
    user: User | AnonymousUser
    cache_versions: dict
    
    @cached_property
    def permissions(self) -> dict:  # 懒加载用户权限
    @cached_property  
    def moderator(self) -> ModeratorPermissions | None:  # 版主权限
    @cached_property
    def moderated_categories(self) -> set[int]:  # 管辖分类
```

#### 4.3.2 权限层级

- **全局权限**: 用户级（能否发帖、上传、点赞等）
- **分类权限**: 按分类控制（浏览、查看、回复等）
- **版主权限**: 全局版主 / 分类版主

权限通过 `permissions_id` 和 `acl_key` 缓存，支持快速验证。

### 4.4 发帖系统

发帖系统采用 **状态机 + 表单集** 的架构：

#### 4.4.1 状态管理 (`State`)

```python
class State:
    request: HttpRequest
    timestamp: datetime
    user: User
    user_permissions: UserPermissionsProxy
    category: Category
    thread: Thread
    post: Post
    parsing_result: ParsingResult
    attachments: list[Attachment]
    state: dict           # 对象初始状态快照
    plugin_state: dict    # 插件状态
    context_data: dict    # 模板上下文
```

核心方法：
- `store_object_state(obj)` / `get_object_state(obj)` - 保存/获取对象快照
- `get_object_changed_fields(obj)` - 计算变更字段
- `update_object(obj)` - 增量更新对象
- `set_thread_title(title)` / `set_post_content(parsing_result)` - 设置内容
- `save_attachments()` - 保存附件

#### 4.4.2 表单集 (`Formset` / `TabbedFormset`)

支持多标签页分组：

```python
class Formset:
    title: TitleForm | None      # 标题表单
    post: PostForm | None        # 内容表单
    members: MembersForm | None  # 成员表单（私密主题）
    errors: list[ValidationError]

class TabbedFormset(Formset):
    tabs: dict[str, FormsetTab]  # 多标签页
```

#### 4.4.3 发帖子状态

- `StartState` → `ThreadStartState` / `PrivateThreadStartState`
- `ReplyState` → `ThreadReplyState` / `PrivateThreadReplyState`
- `PostEditState` → `ThreadPostEditState` / `PrivateThreadPostEditState`

### 4.5 标记语言解析器

解析器基于 `markdown-it-py` 实现，流程分为四步：

1. **创建上下文** (`ParserContext`): 包含用户、权限、设置等信息
2. **创建解析器** (`create_parser`): 基于上下文创建解析器实例
3. **分词** (`tokenize`): 将字符串解析为 AST
4. **渲染** (`render_tokens_to_html` / `render_tokens_to_plaintext`): 输出 HTML 或纯文本

```python
@dataclass(frozen=True)
class ParsingResult:
    markup: str          # 原始标记
    tokens: list[Token]  # AST
    html: str            # HTML 渲染结果
    text: str            # 纯文本
    metadata: dict       # 元数据（如 @mention 用户等）
```

解析器支持通过 Hook 扩展：
- `create_parser_hook` - 自定义解析器
- `process_post_content_hook` - 处理帖子内容
- `highlight_post_code_blocks_hook` - 代码高亮
- `replace_rich_text_tokens_hook` - 替换富文本 token

---

## 5. 数据模型

### 5.1 核心模型

#### User (`misago.users.models.User`)

继承 `AbstractBaseUser`, `PluginDataModel`, `PermissionsMixin`：

| 字段 | 类型 | 说明 |
|------|------|------|
| username / slug | CharField | 用户名和 slug（用于 URL 和搜索） |
| email / email_hash | EmailField / CharField | 邮箱和 MD5 哈希（唯一约束） |
| joined_on / joined_from_ip | DateTimeField / GenericIPAddressField | 注册时间和 IP |
| rank / group / groups_ids | FK / FK / ArrayField | 等级、主用户组、所有用户组 ID |
| permissions_id | CharField(12) | 权限 ID（基于用户组计算） |
| roles | ManyToManyField | ACL 角色 |
| acl_key | CharField(12) | ACL 缓存键 |
| is_misago_root | BooleanField | 超级管理员标记 |
| require_content_approval | BooleanField | 内容需要审核 |
| avatar_* | ImageField | 头像相关字段 |
| signature / signature_parsed / signature_checksum | TextField | 签名 |
| follows / blocks | ManyToManyField | 关注 / 屏蔽 |
| threads / posts | PositiveIntegerField | 发帖计数 |
| last_posted_at | DateTimeField | 最后发帖时间 |
| profile_fields | HStoreField | 自定义资料字段 |
| plugin_data | JSONField | 插件数据 |

#### Thread (`misago.threads.models.Thread`)

继承 `PluginDataModel`：

| 字段 | 类型 | 说明 |
|------|------|------|
| category | FK(Category) | 所属分类 |
| title / slug | CharField(255) | 标题和 slug |
| replies | PositiveIntegerField | 回复数 |
| has_events / has_poll / has_reported_posts | BooleanField | 包含事件/投票/举报 |
| has_unapproved_posts / has_hidden_posts | BooleanField | 包含未审核/隐藏帖子 |
| started_at / last_posted_at | DateTimeField | 创建/最后回复时间 |
| first_post / starter | FK(Post) / FK(User) | 首帖和发起人 |
| last_post / last_poster | FK(Post) / FK(User) | 最后帖子和回复者 |
| pinned | PositiveIntegerField | 置顶状态（无/分类/全局） |
| is_unapproved / is_locked / is_hidden | BooleanField | 审核/锁定/隐藏状态 |
| solution | FK(Post) | 采纳答案 |
| plugin_data | JSONField | 插件数据 |

**关键方法**: `delete()`, `merge(other_thread)`, `move(new_category)`

#### Post (`misago.threads.models.Post`)

继承 `PluginDataModel`：

| 字段 | 类型 | 说明 |
|------|------|------|
| category / thread | FK | 所属分类和主题 |
| poster / poster_name | FK(User) / CharField | 发帖人 |
| content / content_parsed | TextField | 原始内容 / 解析后 HTML |
| checksum | CharField(64) | 内容校验和 |
| metadata | JSONField | 解析元数据 |
| attachments_cache | JSONField | 附件缓存 |
| posted_at / updated_at | DateTimeField | 发布/更新时间 |
| edits / last_editor / last_editor_name | ... | 编辑信息 |
| is_locked / is_hidden | BooleanField | 锁定/隐藏 |
| has_reports / has_open_reports / is_unapproved | BooleanField | 举报/审核 |
| likes / last_likes | PositiveIntegerField / JSONField | 点赞数/最近点赞 |
| search_document / search_vector | TextField / SearchVectorField | 全文搜索 |
| plugin_data | JSONField | 插件数据 |

#### Category (`misago.categories.models.Category`)

继承 `MPTTModel`, `PluginDataModel`，使用 django-mptt 实现树形结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| parent | TreeForeignKey | 父分类 |
| special_role | CharField | 特殊角色 |
| name / slug / short_name / color | ... | 显示信息 |
| description / css_class | TextField / CharField | 描述和 CSS 类 |
| enable_polls / enable_solutions | BooleanField | 启用投票/采纳 |
| delay_browse_check / show_started_only | BooleanField | 浏览控制 |
| is_vanilla / list_children_threads | BooleanField | 显示设置 |
| children_categories_component | CharField | 子分类组件类型 |
| threads / posts / unapproved_threads / unapproved_posts | PositiveIntegerField | 统计计数 |
| last_posted_at / last_thread / last_poster | ... | 最后帖子信息 |
| require_thread_approval / require_reply_approval | BooleanField | 审核设置 |
| prune_started_after / prune_replied_after | PositiveIntegerField | 自动清理设置 |
| archive_pruned_in | FK(self) | 归档分类 |
| plugin_data | JSONField | 插件数据 |

使用 `MPTTModel` 管理分类树，支持无限层级嵌套。

### 5.2 功能模型

#### Poll / PollVote (`misago.polls.models`)

投票系统：
- **Poll**: 问题、选项(JSON)、时长、最大可选数、是否公开、是否允许改票
- **PollVote**: 投票记录，关联用户和选项

#### Attachment (`misago.attachments.models`)

附件系统，支持缩略图、文件类型识别、GIF 动画处理。

#### Notification (`misago.notifications.models`)

通知系统，支持动词(verb)分类、已读/未读状态、关联内容。

#### PostEdit (`misago.postedits.models`)

帖子编辑历史，记录新旧内容、附件变化、隐藏状态。

#### ThreadEvent (`misago.threadevents.models`)

主题事件，支持泛型关联（`context_type` + `context_id`），记录操作人、事件类型。

#### WatchedThread (`misago.notifications.models`)

关注主题，支持邮件通知、退订密钥。

---

## 6. API 层

### 6.1 REST API (`misago.apiv2`)

基于 Django REST Framework：
- 分页: 游标分页 (`CursorPagination`)
- 通知: 通知列表 API
- 用户端点: 用户相关 API

### 6.2 GraphQL API (`misago.graphql`)

基于 Ariadne 实现：
- Schema-first 设计
- 管理面板支持

### 6.3 路由

- 主论坛: `http://127.0.0.1:8000/`
- 管理面板: `http://127.0.0.1:8000/admincp/`
- 健康检查: 返回 `{"status": "OK"}`

---

## 7. 中间件

### 7.1 ExceptionHandlerMiddleware

处理 Misago 异常，支持 HTMX 请求的异常格式。

### 7.2 FrontendContextMiddleware

为每个请求初始化 `frontend_context` 字典，用于向前端传递服务器端数据。

---

## 8. 配置系统

`misago.conf.settings` 是一个 `StaticSettings` 实例，先尝试从 Django settings 获取，失败后从 `misago.conf.defaults` 获取默认值。

---

## 9. 开发环境

### 9.1 Docker 开发

```bash
# 初始化开发环境
./dev init

# 启动开发服务器
docker compose up

# 运行测试
./dev test

# 重建容器
./dev rebuild
```

### 9.2 前端开发

```bash
npm run build    # 生产构建
npm run start    # 开发构建（热重载）
npm run prettier # 代码格式化
npm run eslint   # 代码检查
```

### 9.3 翻译

```bash
./dev makemessages      # 更新英文翻译
./dev compilemessages   # 编译翻译文件
./dev txsync            # 同步 Transifex
```

---

## 10. 功能特性

### 10.1 用户系统
- 用户注册、邮箱验证
- 社交登录（50+ OAuth 提供商）
- 可变头像、自定义资料字段
- 用户名修改、账户删除
- 关注/屏蔽系统
- 在线状态

### 10.2 论坛功能
- 无限层级分类
- 主题置顶（分类/全局）
- 主题锁定/隐藏
- 帖子编辑（带编辑历史）
- Markdown + BBCode 混合解析
- 附件上传（自动缩略图）
- 投票系统（公开/匿名、单选/多选、限时）
- 点赞系统
- Q&A 采纳答案
- 全文搜索

### 10.3 私密主题
- 仅邀请成员可见
- 支持添加/移除成员
- 支持转让所有者

### 10.4 审核系统
- 内容审核队列
- 分类级审核设置
- 版主管理工具

### 10.5 通知系统
- 站内通知
- 邮件通知
- 可自定义通知类型

### 10.6 权限系统
- 基于用户组和角色
- 分类级权限控制
- 版主权限
- 细粒度操作权限

### 10.7 合规性
- GDPR 合规工具
- 用户数据下载
- 账户匿名化删除

---

## 11. 插件开发要点

### 11.1 插件结构

```
my-plugin/
    my_plugin/
        __init__.py
        misago_plugin.py    # 插件清单
        apps.py             # Django AppConfig
        models.py           # 数据模型
        migrations/         # 数据库迁移
        templates/          # 模板
        static/             # 静态文件
```

### 11.2 扩展点

1. **Hooks**: 在预定义位置注入代码（Action / Filter）
2. **Extensions**: 通过 `@extends` 扩展已有类
3. **Template Outlets**: 在模板中插入 HTML
4. **URLs**: 插件 URL 自动包含，可覆盖 Misago 默认 URL
5. **Templates**: 可覆盖 Misago 默认模板
6. **Plugin Data**: 通过 `plugin_data` JSON 字段存储数据

### 11.3 注册 Hooks

在 `apps.py` 的 `ready()` 方法中注册：

```python
from django.apps import AppConfig
from misago.threads.hooks import create_thread_hook

class MyPluginConfig(AppConfig):
    name = "my_plugin"
    
    def ready(self):
        from . import hooks  # 导入即执行注册
```

---

## 12. 数据库

- 使用 PostgreSQL 作为主数据库
- 利用 PostgreSQL 特性：JSONField、ArrayField、HStoreField、GIN/GiST 索引、SearchVectorField 全文搜索
- 通过 `django-mptt` 实现分类树
- 使用 Celery + Redis 处理异步任务

---

## 13. 测试

- 使用 pytest 框架
- 每个模块都有 `tests/` 目录
- 提供 `testutils` 模块辅助测试
- 运行命令: `./dev test`

---

*本文档基于 Misago 0.40.0 版本代码库生成，与项目代码实际结构对应。*